import os
import json
import base64
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import streamlit as st

class GitHubStorage:
    """GitHub-based storage for persistent hypothesis data in Streamlit Cloud"""
    
    def __init__(self, repo_owner: str, repo_name: str, token: str, branch: str = "main"):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.token = token
        self.branch = branch
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.hypotheses_dir = "artifacts/saved_hypotheses"
        
    def _make_request(self, method: str, url: str, data: Optional[Dict] = None) -> Dict:
        """Make authenticated request to GitHub API"""
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=self.headers)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=self.headers, json=data)
            elif method.upper() == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            st.error(f"GitHub API error: {str(e)}")
            return {}
    
    def _get_file_content(self, file_path: str) -> Optional[str]:
        """Get file content from GitHub repository"""
        url = f"{self.base_url}/contents/{file_path}"
        response = self._make_request("GET", url)
        
        if "content" in response:
            # Decode base64 content
            content = base64.b64decode(response["content"]).decode('utf-8')
            return content
        return None
    
    def _create_or_update_file(self, file_path: str, content: str, message: str) -> bool:
        """Create or update file in GitHub repository"""
        url = f"{self.base_url}/contents/{file_path}"
        
        # Check if file exists to get SHA
        existing_file = self._make_request("GET", url)
        sha = existing_file.get("sha") if existing_file else None
        
        # Prepare data
        data = {
            "message": message,
            "content": base64.b64encode(content.encode('utf-8')).decode('utf-8'),
            "branch": self.branch
        }
        
        if sha:
            data["sha"] = sha
            
        response = self._make_request("PUT", url, data)
        return "content" in response
    
    def _delete_file(self, file_path: str, message: str) -> bool:
        """Delete file from GitHub repository"""
        url = f"{self.base_url}/contents/{file_path}"
        
        # Get file SHA first
        file_info = self._make_request("GET", url)
        if "sha" not in file_info:
            return False
            
        data = {
            "message": message,
            "sha": file_info["sha"],
            "branch": self.branch
        }
        
        response = self._make_request("DELETE", url, data)
        return response == {}
    
    def save_hypothesis(self, session_data: Dict[str, Any]) -> bool:
        """Save hypothesis data to GitHub repository"""
        try:
            hyp_id = session_data["hypothesis"].get("id", f"H{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            # Save JSON data - GitHub will create the directory structure automatically
            json_file_path = f"{self.hypotheses_dir}/{hyp_id}.json"
            json_content = json.dumps(session_data, indent=2, ensure_ascii=False, default=str)
            
            message = f"Save hypothesis {hyp_id} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            success = self._create_or_update_file(json_file_path, json_content, message)
            
            if not success:
                return False
                
            # Save images if they exist
            if session_data.get("original_screenshot"):
                original_img_path = f"{self.hypotheses_dir}/{hyp_id}_original.png"
                # Ensure we have bytes data
                img_data = session_data["original_screenshot"]
                if hasattr(img_data, 'read'):  # If it's a file-like object
                    img_data = img_data.read()
                elif isinstance(img_data, (str, Path)):  # If it's a path (string or Path object)
                    with open(img_data, 'rb') as f:
                        img_data = f.read()
                elif not isinstance(img_data, bytes):  # If it's not bytes, try to convert
                    img_data = bytes(img_data)
                img_content = base64.b64encode(img_data).decode('utf-8')
                self._create_or_update_file(original_img_path, img_content, f"Save original image for {hyp_id}")
            
            if session_data.get("generated_image"):
                generated_img_path = f"{self.hypotheses_dir}/{hyp_id}_generated.png"
                # Ensure we have bytes data
                img_data = session_data["generated_image"]
                if hasattr(img_data, 'read'):  # If it's a file-like object
                    img_data = img_data.read()
                elif isinstance(img_data, (str, Path)):  # If it's a path (string or Path object)
                    with open(img_data, 'rb') as f:
                        img_data = f.read()
                elif not isinstance(img_data, bytes):  # If it's not bytes, try to convert
                    img_data = bytes(img_data)
                img_content = base64.b64encode(img_data).decode('utf-8')
                self._create_or_update_file(generated_img_path, img_content, f"Save generated image for {hyp_id}")
            
            return True
            
        except Exception as e:
            st.error(f"Error saving hypothesis to GitHub: {str(e)}")
            return False
    

    def load_hypotheses(self) -> List[Dict[str, Any]]:
        """Load all saved hypotheses from GitHub repository"""
        try:
            # Get list of files in hypotheses directory
            url = f"{self.base_url}/contents/{self.hypotheses_dir}"
            files = self._make_request("GET", url)
            
            # If directory doesn't exist yet, return empty list
            if not isinstance(files, list):
                return []
            
            loaded_sessions = []
            for file_info in files:
                if file_info.get("name", "").endswith(".json"):
                    file_path = file_info["path"]
                    content = self._get_file_content(file_path)
                    
                    if content:
                        try:
                            session_data = json.loads(content)
                            loaded_sessions.append(session_data)
                        except json.JSONDecodeError:
                            continue
            
            return loaded_sessions
            
        except Exception as e:
            # If directory doesn't exist, return empty list instead of error
            if "404" in str(e):
                return []
            st.error(f"Error loading hypotheses from GitHub: {str(e)}")
            return []
    
    def delete_hypothesis(self, hyp_id: str) -> bool:
        """Delete hypothesis files from GitHub repository"""
        try:
            # Delete JSON file
            json_file_path = f"{self.hypotheses_dir}/{hyp_id}.json"
            message = f"Delete hypothesis {hyp_id} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            success = self._delete_file(json_file_path, message)
            
            # Delete associated images
            original_img_path = f"{self.hypotheses_dir}/{hyp_id}_original.png"
            generated_img_path = f"{self.hypotheses_dir}/{hyp_id}_generated.png"
            
            self._delete_file(original_img_path, f"Delete original image for {hyp_id}")
            self._delete_file(generated_img_path, f"Delete generated image for {hyp_id}")
            
            return success
            
        except Exception as e:
            st.error(f"Error deleting hypothesis from GitHub: {str(e)}")
            return False
    
    def get_hypothesis_image(self, hyp_id: str, image_type: str = "original") -> Optional[bytes]:
        """Get hypothesis image from GitHub repository"""
        try:
            image_path = f"{self.hypotheses_dir}/{hyp_id}_{image_type}.png"
            content = self._get_file_content(image_path)
            
            if content:
                return base64.b64decode(content)
            return None
            
        except Exception as e:
            st.error(f"Error loading image from GitHub: {str(e)}")
            return None


def get_github_storage() -> Optional[GitHubStorage]:
    """Initialize GitHub storage with environment variables"""
    try:
        # Get configuration from environment variables or Streamlit secrets
        # repo_owner = os.getenv("GITHUB_REPO_OWNER") or st.secrets.get("github.repo_owner")
        # repo_name = os.getenv("GITHUB_REPO_NAME") or st.secrets.get("github.repo_name")
        # token = os.getenv("GITHUB_TOKEN") or st.secrets.get("github.token")
        
        # Fallback to hardcoded values for development
        # if not repo_owner:
        repo_owner = 'nikhil-exl'
        # if not repo_name:
        repo_name = 'experimentation_agent'
            # repo_name = 'experimentation_agent'
        # if not token:
        token = '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'
            # token = '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'
        
        if not all([repo_owner, repo_name, token]):
            st.warning("GitHub storage not configured. Please set GITHUB_REPO_OWNER, GITHUB_REPO_NAME, and GITHUB_TOKEN environment variables or add them to Streamlit secrets.")
            return None
            
        return GitHubStorage(repo_owner, repo_name, token)
        
    except Exception as e:
        st.error(f"Failed to initialize GitHub storage: {str(e)}")
        return None

