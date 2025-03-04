import requests
import boto3
import io
import os
import json

def download_from_graph_to_s3(folder_id, access_token, s3_bucket_name, s3_prefix="", s3_client=None):
    """
    Downloads files and folders recursively from a Microsoft Graph URL and uploads them to AWS S3.

    Args:
        folder_id (str): The Microsoft Graph object_id to start downloading from.
                           Example: "https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}/children"
        access_token (str): Your Microsoft Graph access token.
        s3_bucket_name (str): The name of the AWS S3 bucket to upload files to.
        s3_prefix (str, optional):  An optional prefix to add to the S3 keys. Defaults to "".
        s3_client (boto3.client, optional):  Pre-initialized boto3 S3 client. If None, a new client will be created.
                                            Defaults to None.

    Returns:
        None
    """
    graph_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}/children"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }

    if s3_client is None:
        s3_client = boto3.client('s3')

    def _upload_folder_contents_to_s3(folder_url, s3_current_prefix):
        """
        Recursive helper function to download contents of a folder and upload to S3.

        Args:
            folder_url (str): The Graph URL for the folder's children.
            s3_current_prefix (str): The S3 key prefix for this folder.
        """
        try:
            response = requests.get(folder_url, headers=headers)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()

            if 'value' in data:
                for item in data['value']:
                    item_id = item['id']  # ID of the item in OneDrive
                    item_name = item['name']
                    s3_key = os.path.join(s3_current_prefix, item_name).replace("\\", "/") # Ensure forward slashes for S3 keys

                    if 'folder' in item:  # It's a folder
                        print(f"Creating S3 folder prefix: s3://{s3_bucket_name}/{s3_key}/") # S3 "folders" are prefixes
                        folder_children_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{item_id}/children"
                        _upload_folder_contents_to_s3(folder_children_url, s3_key)  # Recursive call for subfolder

                    elif 'file' in item:  # It's a file
                        download_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{item_id}/content"
                        print(f"Downloading file: {item_name} and uploading to s3://{s3_bucket_name}/{s3_key}")
                        try:
                            file_response = requests.get(download_url, headers=headers, stream=True) # stream=True for large files
                            file_response.raise_for_status()

                            s3_client.upload_fileobj(
                                file_response.raw,  # Use raw stream content for efficient upload
                                s3_bucket_name,
                                s3_key
                            )

                        except requests.exceptions.RequestException as e:
                            print(f"Error downloading file '{item_name}': {e}")
                        except Exception as e: # Catch potential boto3 or other upload errors
                            print(f"Error uploading file '{item_name}' to S3: {e}")

                # Handle pagination if more items are available
                if '@odata.nextLink' in data:
                    next_page_url = data['@odata.nextLink']
                    print(f"Fetching next page: {next_page_url}")
                    _upload_folder_contents_to_s3(next_page_url, s3_current_prefix) # Recursive call for next page

            else:
                print(f"No 'value' key found in response. Unexpected response structure: {data}")

        except requests.exceptions.RequestException as e:
            print(f"Error accessing folder URL '{folder_url}': {e}")
        except json.JSONDecodeError:
            print(f"Error decoding JSON response from URL '{folder_url}'. Response content: {response.text}")


    print(f"Starting download from: {graph_url} and uploading to s3://{s3_bucket_name}/{s3_prefix}")
    _upload_folder_contents_to_s3(graph_url, s3_prefix)
    print("Download and S3 upload completed.")

"""
def download_onedrive_file_to_s3(onedrive_file_id, access_token, s3_object_key, s3_bucket_name = "assist-poc-bucket", drive_id=None):
    ""
    Downloads a file from OneDrive using Microsoft Graph API and uploads it to AWS S3.

    Args:
        onedrive_file_id (str): The ID of the file in OneDrive.
        access_token (str): The Microsoft Graph API access token.
        s3_bucket_name (str): The name of the AWS S3 bucket to upload to.
        s3_object_key (str): The key (path/filename) for the object in S3.
        drive_id (str, optional): The ID of the OneDrive drive.
                                   Required if the file is not in the user's default drive.
                                   If None, it assumes the file is in the user's root drive.

    Returns:
        bool: True if the download and upload were successful, False otherwise.
                Prints error messages to console in case of failure.
    ""
    try:
        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        # Construct the Microsoft Graph API endpoint for downloading file content
        if drive_id:
            download_url = f'https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{onedrive_file_id}/content'
        else:
            download_url = f'https://graph.microsoft.com/v1.0/me/drive/items/{onedrive_file_id}/content'

        response = requests.get(download_url, headers=headers, stream=True)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        if response.status_code == 200:
            print(f"Successfully downloaded file content from OneDrive (File ID: {onedrive_file_id})")

            # Initialize S3 client
            s3_client = boto3.client('s3')  # Assumes AWS credentials are configured (e.g., env vars, IAM roles)

            try:
                # Upload the file content stream directly to S3
                s3_client.upload_fileobj(response.raw, s3_bucket_name, s3_object_key)
                print(f"Successfully uploaded file to S3 bucket '{s3_bucket_name}' with key '{s3_object_key}'")
                return True

            except Exception as e_s3:
                print(f"Error uploading to S3: {e_s3}")
                return False
        else:
            print(f"Failed to download file content from OneDrive. Status Code: {response.status_code}, Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e_request:
        print(f"Request error during OneDrive file download: {e_request}")
        return False
    except Exception as e_general:
        print(f"An unexpected error occurred: {e_general}")
        return False

if __name__ == '__main__':
    # --- Replace with your actual values ---
    onedrive_file_id_example = "YOUR_ONEDRIVE_FILE_ID"  # Example: "0123456789abcdef!123"
    onedrive_access_token_example = "YOUR_MICROSOFT_GRAPH_ACCESS_TOKEN" # Obtain this through OAuth 2.0 flow
    s3_bucket_name_example = "your-s3-bucket-name"
    s3_object_key_example = "onedrive-files/example-file.pdf" # Example: "onedrive-files/document.pdf"
    onedrive_drive_id_example = None # or "YOUR_ONEDRIVE_DRIVE_ID" if not using default drive

    # You would typically obtain the access token through an OAuth 2.0 flow
    # For testing, you might temporarily use a manually obtained token from the Graph Explorer:
    # https://developer.microsoft.com/en-us/graph/graph-explorer

    if onedrive_file_id_example == "YOUR_ONEDRIVE_FILE_ID" or onedrive_access_token_example == "YOUR_MICROSOFT_GRAPH_ACCESS_TOKEN" or s3_bucket_name_example == "your-s3-bucket-name":
        print("Please replace the placeholder values in the __main__ section with your actual OneDrive File ID, Access Token, and S3 bucket details.")
    else:
        success = download_onedrive_file_to_s3(
            onedrive_file_id=onedrive_file_id_example,
            access_token=onedrive_access_token_example,
            s3_bucket_name=s3_bucket_name_example,
            s3_object_key=s3_object_key_example,
            drive_id=onedrive_drive_id_example # Optional drive ID
        )

        if success:
            print("OneDrive file download and S3 upload process completed successfully.")
        else:
            print("OneDrive file download and S3 upload process failed. See error messages above.")
            """