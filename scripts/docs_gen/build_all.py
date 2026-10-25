import os
import sys

# Ensure root workspace and scripts/docs_gen are on sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, "scripts"))

from docs_gen.gen_overview import generate_overview
from docs_gen.gen_features import generate_features
from docs_gen.gen_architecture import generate_architecture
from docs_gen.gen_interview_qa import generate_interview_qa
from docs_gen.gen_checklist import generate_checklist
from docs_gen.gen_system_design import generate_system_design
from docs_gen.gen_vitepress_config import generate_vitepress_config

def main():
    docs_dir = os.path.join(root_dir, "docs")
    print(f"Starting Ultimate Documentation Generator for: {root_dir}")
    print(f"Output Target Directory: {docs_dir}")

    generate_overview(docs_dir)
    generate_features(docs_dir)
    generate_architecture(docs_dir)
    generate_interview_qa(docs_dir)
    generate_checklist(docs_dir)
    generate_system_design(docs_dir)
    generate_vitepress_config(docs_dir)

    print("\n[SUCCESS] All documentation chapters generated successfully!")

if __name__ == "__main__":
    main()
