import os
import git
from app.config import TENANTS_DIR

def get_tenant_repo_dir(tenant_id: str) -> str:
    """Returns the absolute directory path where the tenant's git repository is stored."""
    return os.path.join(TENANTS_DIR, tenant_id, "repo")

def init_tenant_repo(tenant_id: str) -> git.Repo:
    """
    Initializes a new Git repository for the tenant if it doesn't already exist.
    Creates an initial commit with a README to set up the main branch.
    """
    repo_dir = get_tenant_repo_dir(tenant_id)
    os.makedirs(repo_dir, exist_ok=True)
    
    if os.path.exists(os.path.join(repo_dir, ".git")):
        return git.Repo(repo_dir)
        
    repo = git.Repo.init(repo_dir)
    
    # Create a default README.md
    readme_path = os.path.join(repo_dir, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(f"# Cortex Knowledge OS - Repository for Tenant [{tenant_id}]\n")
        
    # Commit initial readme
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit: Setup tenant knowledge base")
    
    return repo

def commit_page_changes(tenant_id: str, page_id: str, commit_message: str) -> str:
    """
    Stages and commits a specific page file in the tenant's Git repository.
    Returns the hex sha of the commit.
    """
    repo = init_tenant_repo(tenant_id)
    repo_dir = get_tenant_repo_dir(tenant_id)
    
    # Construct relative path to the repo root for git staging
    # Pages are stored in the root of the repo dir
    page_filename = f"{page_id}.md"
    page_path = os.path.join(repo_dir, page_filename)
    
    if not os.path.exists(page_path):
        raise FileNotFoundError(f"Page file {page_filename} not found in repository.")
        
    repo.index.add([page_filename])
    commit = repo.index.commit(commit_message)
    return commit.hexsha
