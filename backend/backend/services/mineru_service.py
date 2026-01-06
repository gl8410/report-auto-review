"""
MinerU API Service for document parsing
Handles batch file upload and parsing using MinerU API
"""
import os
import time
import zipfile
import io
import requests
from typing import List, Dict, Optional, Tuple
from backend.core.config import settings


class MinerUService:
    """Service for interacting with MinerU API"""
    
    BASE_URL = "https://mineru.net/api/v4"
    MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB in bytes
    POLL_INTERVAL = 5  # seconds
    MAX_POLL_ATTEMPTS = 360  # 30 minutes max (360 * 5 seconds)
    
    def __init__(self):
        self.api_key = settings.MINERU_KEY
        if not self.api_key:
            raise ValueError("MINERU_KEY not found in environment variables")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers for MinerU API"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def validate_file_size(self, file_size: int) -> Tuple[bool, Optional[str]]:
        """
        Validate file size is within MinerU limits
        Returns: (is_valid, error_message)
        """
        if file_size > self.MAX_FILE_SIZE:
            size_mb = file_size / (1024 * 1024)
            return False, f"File size ({size_mb:.1f}MB) exceeds 200MB limit"
        return True, None
    
    def request_upload_urls(
        self, 
        files: List[Dict[str, str]], 
        model_version: str = "vlm"
    ) -> Tuple[Optional[str], Optional[List[str]], Optional[str]]:
        """
        Request upload URLs from MinerU for batch file upload
        
        Args:
            files: List of dicts with 'name' and optional 'data_id'
            model_version: MinerU model version (default: vlm)
            
        Returns:
            (batch_id, upload_urls, error_message)
        """
        url = f"{self.BASE_URL}/file-urls/batch"
        
        payload = {
            "files": files,
            "model_version": model_version,
            "enable_formula": True,
            "enable_table": True,
            "language": "ch"
        }
        
        try:
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    data = result.get("data", {})
                    batch_id = data.get("batch_id")
                    file_urls = data.get("file_urls", [])
                    return batch_id, file_urls, None
                else:
                    return None, None, result.get("msg", "Unknown error from MinerU")
            else:
                return None, None, f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.Timeout:
            return None, None, "Request timeout - MinerU API did not respond in time"
        except Exception as e:
            return None, None, f"Failed to request upload URLs: {str(e)}"
    
    def upload_file_to_url(self, file_content: bytes, upload_url: str) -> Tuple[bool, Optional[str]]:
        """
        Upload file content to the provided MinerU upload URL
        
        Returns:
            (success, error_message)
        """
        try:
            # MinerU requires PUT request without Content-Type header
            response = requests.put(upload_url, data=file_content, timeout=300)
            
            if response.status_code == 200:
                return True, None
            else:
                return False, f"Upload failed with status {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "Upload timeout - file upload took too long"
        except Exception as e:
            return False, f"Upload error: {str(e)}"
    
    def poll_batch_results(
        self, 
        batch_id: str,
        callback_fn: Optional[callable] = None
    ) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """
        Poll MinerU API for batch processing results
        
        Args:
            batch_id: The batch ID returned from upload
            callback_fn: Optional callback function to report progress
            
        Returns:
            (results_list, error_message)
            results_list contains dicts with: file_name, state, full_zip_url, err_msg
        """
        url = f"{self.BASE_URL}/extract-results/batch/{batch_id}"
        
        for attempt in range(self.MAX_POLL_ATTEMPTS):
            try:
                response = requests.get(url, headers=self._get_headers(), timeout=30)
                
                if response.status_code != 200:
                    return None, f"HTTP {response.status_code}: {response.text}"
                
                result = response.json()
                if result.get("code") != 0:
                    return None, result.get("msg", "Unknown error from MinerU")
                
                data = result.get("data", {})
                extract_results = data.get("extract_result", [])
                
                # Check if all files are done or failed
                all_complete = True
                for file_result in extract_results:
                    state = file_result.get("state", "")
                    if state in ["pending", "running", "converting", "waiting-file"]:
                        all_complete = False
                        
                        # Call progress callback if provided
                        if callback_fn:
                            progress = file_result.get("extract_progress", {})
                            callback_fn(
                                file_name=file_result.get("file_name"),
                                state=state,
                                progress=progress
                            )
                        break
                
                if all_complete:
                    return extract_results, None
                
                # Wait before next poll
                time.sleep(self.POLL_INTERVAL)
                
            except requests.exceptions.Timeout:
                # Continue polling on timeout
                time.sleep(self.POLL_INTERVAL)
                continue
            except Exception as e:
                return None, f"Polling error: {str(e)}"
        
        return None, "Parsing timeout - exceeded maximum wait time (30 minutes)"
    
    def download_and_extract_markdown(self, zip_url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Download the result ZIP file and extract the markdown content
        
        Returns:
            (markdown_content, error_message)
        """
        try:
            # Download ZIP file
            response = requests.get(zip_url, timeout=300)
            if response.status_code != 200:
                return None, f"Failed to download results: HTTP {response.status_code}"
            
            # Extract markdown from ZIP
            zip_content = io.BytesIO(response.content)
            
            with zipfile.ZipFile(zip_content, 'r') as zip_ref:
                # Look for .md file in the ZIP
                md_files = [f for f in zip_ref.namelist() if f.endswith('.md')]
                
                if not md_files:
                    return None, "No markdown file found in result ZIP"
                
                # Use the first markdown file (usually there's only one)
                md_filename = md_files[0]
                markdown_content = zip_ref.read(md_filename).decode('utf-8')
                
                return markdown_content, None
                
        except zipfile.BadZipFile:
            return None, "Downloaded file is not a valid ZIP archive"
        except requests.exceptions.Timeout:
            return None, "Download timeout - result file download took too long"
        except Exception as e:
            return None, f"Failed to extract markdown: {str(e)}"
    
    def process_files(
        self,
        files_data: List[Dict[str, any]],
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, any]]:
        """
        Complete workflow: upload files to MinerU, wait for processing, download results
        
        Args:
            files_data: List of dicts with 'name', 'content' (bytes), 'data_id'
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of results with: success, file_name, markdown_content, error_message
        """
        results = []
        
        # Step 1: Request upload URLs
        file_requests = [{"name": f["name"], "data_id": f.get("data_id", "")} for f in files_data]
        batch_id, upload_urls, error = self.request_upload_urls(file_requests)
        
        if error or not batch_id or not upload_urls:
            # All files failed
            for file_data in files_data:
                results.append({
                    "success": False,
                    "file_name": file_data["name"],
                    "markdown_content": None,
                    "error_message": error or "Failed to get upload URLs"
                })
            return results
        
        # Step 2: Upload files
        for i, file_data in enumerate(files_data):
            if i >= len(upload_urls):
                results.append({
                    "success": False,
                    "file_name": file_data["name"],
                    "markdown_content": None,
                    "error_message": "No upload URL provided for this file"
                })
                continue
            
            success, error = self.upload_file_to_url(file_data["content"], upload_urls[i])
            if not success:
                results.append({
                    "success": False,
                    "file_name": file_data["name"],
                    "markdown_content": None,
                    "error_message": error
                })
        
        # Step 3: Poll for results
        extract_results, error = self.poll_batch_results(batch_id, progress_callback)
        
        if error or not extract_results:
            # Update all results with polling error
            for result in results:
                if result.get("success") is None:  # Not yet processed
                    result["success"] = False
                    result["error_message"] = error or "Failed to get parsing results"
            return results
        
        # Step 4: Download and extract markdown for each successful file
        for extract_result in extract_results:
            file_name = extract_result.get("file_name", "")
            state = extract_result.get("state", "")
            
            if state == "done":
                zip_url = extract_result.get("full_zip_url")
                if zip_url:
                    markdown, error = self.download_and_extract_markdown(zip_url)
                    results.append({
                        "success": markdown is not None,
                        "file_name": file_name,
                        "markdown_content": markdown,
                        "error_message": error,
                        "zip_url": zip_url
                    })
                else:
                    results.append({
                        "success": False,
                        "file_name": file_name,
                        "markdown_content": None,
                        "error_message": "No download URL provided"
                    })
            else:
                # Failed or other state
                results.append({
                    "success": False,
                    "file_name": file_name,
                    "markdown_content": None,
                    "error_message": extract_result.get("err_msg", f"Parsing failed with state: {state}")
                })
        
        return results


# Singleton instance
mineru_service = MinerUService()

