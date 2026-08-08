from __future__ import annotations

import hashlib
import json
from pathlib import Path

EXTERNAL_SKILLS_PATH = Path(r"C:\Users\contr\dev\external\google-skills")
COMMIT_SHA = "092e210b243601797a0fb939040be2b1288e6d39"

def generate_manifest() -> dict[str, object]:
    skills_dir = EXTERNAL_SKILLS_PATH / "skills"
    skill_entries = []
    
    for skill_file in sorted(skills_dir.rglob("SKILL.md"), key=lambda p: p.as_posix()):
        rel_path = skill_file.relative_to(EXTERNAL_SKILLS_PATH).as_posix()
        content = skill_file.read_bytes()
        content_hash = hashlib.sha256(content).hexdigest()
        
        # Simple extraction of skill name from folder or frontmatter
        folder_name = skill_file.parent.name
        
        skill_entries.append({
            "name": folder_name,
            "path": rel_path,
            "hash": content_hash,
            "bytes": len(content),
        })
        
    manifest = {
        "google_skills_commit": COMMIT_SHA,
        "skill_count": len(skill_entries),
        "skills": skill_entries,
    }
    
    return manifest

if __name__ == "__main__":
    manifest = generate_manifest()
    out_path = Path.cwd() / "benchmark-skill-manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Generated benchmark-skill-manifest.json with {manifest['skill_count']} skills.")
