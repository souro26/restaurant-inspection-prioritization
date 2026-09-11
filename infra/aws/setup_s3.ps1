param(
    [string]$Bucket = "restaurant-risk-269626332583-ap-south-1",
    [string]$Region = "ap-south-1",
    [string]$IamGroup = "restaurant-risk-ecr-deployer"
)

$ErrorActionPreference = "Stop"

Write-Host "Checking AWS identity..."
aws sts get-caller-identity

Write-Host "Ensuring S3 bucket exists: $Bucket"

aws s3api head-bucket `
    --bucket $Bucket `
    2>$null

if ($LASTEXITCODE -ne 0) {
    aws s3api create-bucket `
        --bucket $Bucket `
        --region $Region `
        --create-bucket-configuration LocationConstraint=$Region
}

Write-Host "Blocking all public access..."

aws s3api put-public-access-block `
    --bucket $Bucket `
    --public-access-block-configuration `
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

Write-Host "Enabling bucket versioning..."

aws s3api put-bucket-versioning `
    --bucket $Bucket `
    --versioning-configuration Status=Enabled

Write-Host "Enabling default SSE-S3 encryption..."

$encryption = @'
{
  "Rules": [
    {
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      },
      "BucketKeyEnabled": true
    }
  ]
}
'@

aws s3api put-bucket-encryption `
    --bucket $Bucket `
    --server-side-encryption-configuration $encryption

Write-Host "Attaching least-privilege artifact policy to IAM group: $IamGroup"

$policy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListBucket",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::$Bucket"
    },
    {
      "Sid": "ReadWriteRestaurantRiskArtifacts",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::$Bucket/*"
    }
  ]
}
"@

$policyFile = Join-Path `
    $env:TEMP `
    "restaurant-risk-s3-policy.json"

$policy |
    Set-Content `
        -Path $policyFile `
        -Encoding UTF8

aws iam put-group-policy `
    --group-name $IamGroup `
    --policy-name restaurant-risk-s3-artifacts `
    --policy-document file://$policyFile

Remove-Item $policyFile -Force

Write-Host "Verifying bucket configuration..."

aws s3api get-bucket-versioning `
    --bucket $Bucket

aws s3api get-public-access-block `
    --bucket $Bucket

aws s3api get-bucket-encryption `
    --bucket $Bucket

Write-Host `
    "S3 artifact storage is ready: s3://$Bucket/restaurant-risk/"