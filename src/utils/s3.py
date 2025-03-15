import boto3
from botocore.exceptions import ClientError
from pathlib import Path
from typing import Optional

from src.config.settings import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_DEFAULT_REGION,
    S3_BUCKET_NAME
)

class S3Client:
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_DEFAULT_REGION
        )
        self.bucket = S3_BUCKET_NAME

    def upload_file(self, file_path: Path, s3_key: str) -> bool:
        """Upload a file to S3."""
        try:
            self.s3.upload_file(str(file_path), self.bucket, s3_key)
            return True
        except ClientError as e:
            print(f"Error uploading file to S3: {e}")
            return False

    def download_file(self, s3_key: str, local_path: Path) -> bool:
        """Download a file from S3."""
        try:
            self.s3.download_file(self.bucket, s3_key, str(local_path))
            return True
        except ClientError as e:
            print(f"Error downloading file from S3: {e}")
            return False

    def get_file_content(self, s3_key: str) -> Optional[bytes]:
        """Get file content from S3."""
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=s3_key)
            return response['Body'].read()
        except ClientError as e:
            print(f"Error getting file content from S3: {e}")
            return None

    def list_files(self, prefix: str = "") -> list:
        """List files in S3 bucket with given prefix."""
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix
            )
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []
        except ClientError as e:
            print(f"Error listing files in S3: {e}")
            return []

    def delete_file(self, s3_key: str) -> bool:
        """Delete a file from S3."""
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=s3_key)
            return True
        except ClientError as e:
            print(f"Error deleting file from S3: {e}")
            return False 