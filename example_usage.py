#!/usr/bin/env python3
"""
Example script demonstrating programmatic usage of CodeSentry
"""

import os
import sys

# Add codesentry to path
sys.path.insert(0, os.path.dirname(__file__))

from codesentry.utils import load_config, get_supported_files
from codesentry.static_analyzer import StaticAnalyzer
from codesentry.code_indexer import CodeIndexer
from codesentry.rag_system import RAGSystem
from codesentry.ai_reviewer import AIReviewer
from codesentry.report_generator import ReportGenerator


def run_code_review(project_path: str, output_dir: str = "reports"):
    """
    Run a complete code review programmatically

    Args:
        project_path: Path to the codebase to review
        output_dir: Directory to save the report
    """
    print(f"Starting code review for: {project_path}\n")

    # Load configuration
    config = load_config("config.yaml")
    config['report']['output_dir'] = output_dir

    # Get files to analyze
    files = get_supported_files(project_path, config)
    print(f"Found {len(files)} files to analyze\n")

    if not files:
        print("No supported files found!")
        return

    # Layer 1: Static Analysis
    print("=" * 60)
    print("LAYER 1: STATIC ANALYSIS")
    print("=" * 60)

    analyzer = StaticAnalyzer(config)
    static_results = analyzer.analyze(files)

    print(f"\nStatic Analysis Summary:")
    print(f"  Total Issues: {static_results['summary'].get('total_issues', 0)}")
    print(f"  Errors: {static_results['summary'].get('severity_breakdown', {}).get('error', 0)}")
    print(f"  Warnings: {static_results['summary'].get('severity_breakdown', {}).get('warning', 0)}")
    print(f"  Security Issues: {static_results['summary'].get('bandit_issues', 0)}")

    # Layer 2: AI Review with RAG
    print("\n" + "=" * 60)
    print("LAYER 2: AI-POWERED REVIEW")
    print("=" * 60)

    # Index code
    print("\nIndexing codebase...")
    indexer = CodeIndexer(config)
    chunks = indexer.index_files(files)

    # Set up RAG
    print("\nSetting up RAG system...")
    rag_system = RAGSystem(config)
    rag_system.index_chunks(chunks)

    # Perform AI review
    print("\nPerforming AI review...")
    reviewer = AIReviewer(config, rag_system)
    ai_results = reviewer.perform_review(files, static_results)

    # Generate report
    print("\n" + "=" * 60)
    print("GENERATING REPORT")
    print("=" * 60)

    report_gen = ReportGenerator(config)
    report_path = report_gen.generate_report(
        static_results,
        ai_results,
        files,
        project_path
    )

    print(f"\n✓ Review complete!")
    print(f"Report saved to: {report_path}")

    return report_path


if __name__ == "__main__":
    # Example usage
    if len(sys.argv) > 1:
        project_path = sys.argv[1]
    else:
        project_path = "."  # Current directory

    # Ensure HF_TOKEN is set
    if not os.getenv('HF_TOKEN'):
        print("Warning: HF_TOKEN environment variable not set!")
        print("AI review may not work without it.\n")

    # Run review
    run_code_review(project_path)
