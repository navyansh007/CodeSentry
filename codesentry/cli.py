"""
CLI Interface for CodeSentry
"""

import click
import os
import sys
from pathlib import Path
from colorama import init, Fore, Style

from .utils import load_config, get_supported_files, ensure_dir
from .static_analyzer import StaticAnalyzer
from .code_indexer import CodeIndexer
from .rag_system import RAGSystem
from .ai_reviewer import AIReviewer
from .report_generator import ReportGenerator

# Initialize colorama for cross-platform colored output
init(autoreset=True)


def print_banner():
    """Print CodeSentry banner"""
    banner = f"""
{Fore.CYAN}╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   {Fore.YELLOW}🛡️  CodeSentry - AI-Powered Code Review System{Fore.CYAN}           ║
║                                                               ║
║   {Fore.WHITE}Static Analysis + AI Review with RAG Architecture{Fore.CYAN}        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
    print(banner)


def get_empty_static_results():
    """Return empty static results structure"""
    return {
        'summary': {
            'total_issues': 0,
            'pylint_issues': 0,
            'flake8_issues': 0,
            'bandit_issues': 0,
            'high_complexity_functions': 0,
            'severity_breakdown': {
                'error': 0,
                'warning': 0,
                'info': 0,
                'security': 0
            }
        },
        'pylint': [],
        'flake8': [],
        'bandit': [],
        'radon': []
    }


@click.command()
@click.option(
    '--path',
    '-p',
    default='.',
    help='Path to the codebase directory to review (default: current directory)'
)
@click.option(
    '--config',
    '-c',
    default='config.yaml',
    help='Path to configuration file (default: config.yaml)'
)
@click.option(
    '--output',
    '-o',
    default=None,
    help='Output directory for reports (overrides config)'
)
@click.option(
    '--no-static',
    is_flag=True,
    help='Skip static analysis'
)
@click.option(
    '--no-ai',
    is_flag=True,
    help='Skip AI review'
)
@click.option(
    '--clear-cache',
    is_flag=True,
    help='Clear ChromaDB cache before analysis'
)
def main(path, config, output, no_static, no_ai, clear_cache):
    """
    CodeSentry - Comprehensive code review tool with static analysis and AI-powered insights

    Example usage:
        codesentry --path ./my-project
        codesentry --path ./src --no-static
        codesentry --clear-cache
    """
    print_banner()

    # Load configuration
    try:
        print(f"{Fore.CYAN}Loading configuration...{Style.RESET_ALL}")

        # Try to find config file
        config_path = config
        if not os.path.exists(config_path):
            # Try to find in package directory
            package_dir = Path(__file__).parent.parent
            config_path = package_dir / "config.yaml"

        if not os.path.exists(config_path):
            print(f"{Fore.RED}Error: Configuration file not found: {config}{Style.RESET_ALL}")
            sys.exit(1)

        cfg = load_config(config_path)
        print(f"{Fore.GREEN}✓ Configuration loaded{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error loading configuration: {str(e)}{Style.RESET_ALL}")
        sys.exit(1)

    # Override output directory if specified
    if output:
        cfg['report']['output_dir'] = output

    # Validate path
    if not os.path.exists(path):
        print(f"{Fore.RED}Error: Path does not exist: {path}{Style.RESET_ALL}")
        sys.exit(1)

    # Convert to absolute path
    path = os.path.abspath(path)
    print(f"{Fore.CYAN}Analyzing codebase: {Fore.YELLOW}{path}{Style.RESET_ALL}\n")

    # Get supported files
    print(f"{Fore.CYAN}Scanning for files...{Style.RESET_ALL}")
    files = get_supported_files(path, cfg)

    if not files:
        print(f"{Fore.RED}No supported files found in {path}{Style.RESET_ALL}")
        sys.exit(1)

    print(f"{Fore.GREEN}✓ Found {len(files)} files to analyze{Style.RESET_ALL}\n")

    # Initialize components
    static_results = None
    ai_results = None

    # ==========================
    # Static Analysis Layer
    # ==========================
    if not no_static:
        print(f"{Fore.CYAN}{'='*60}")
        print(f"LAYER 1: STATIC ANALYSIS")
        print(f"{'='*60}{Style.RESET_ALL}\n")

        try:
            analyzer = StaticAnalyzer(cfg)
            static_results = analyzer.analyze(files)

            print(f"\n{Fore.GREEN}✓ Static analysis complete{Style.RESET_ALL}")
            print(f"  Total issues found: {Fore.YELLOW}{static_results['summary']['total_issues']}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error during static analysis: {str(e)}{Style.RESET_ALL}")
            static_results = get_empty_static_results()
    else:
        print(f"{Fore.YELLOW}Skipping static analysis (--no-static flag){Style.RESET_ALL}")
        static_results = get_empty_static_results()

    # ==========================
    # AI Review Layer with RAG
    # ==========================
    if not no_ai:
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"LAYER 2: AI-POWERED REVIEW WITH RAG")
        print(f"{'='*60}{Style.RESET_ALL}\n")

        try:
            # Check for HF_TOKEN
            if not os.getenv('HF_TOKEN'):
                print(f"{Fore.YELLOW}Warning: HF_TOKEN environment variable not set.")
                print(f"AI review will not work without a valid Hugging Face token.{Style.RESET_ALL}\n")

            # Step 1: Code Indexing
            print(f"{Fore.CYAN}Step 1: Indexing codebase...{Style.RESET_ALL}")
            indexer = CodeIndexer(cfg)
            chunks = indexer.index_files(files)
            print(f"{Fore.GREEN}✓ Code indexing complete{Style.RESET_ALL}\n")

            # Step 2: RAG System Setup
            print(f"{Fore.CYAN}Step 2: Setting up RAG system...{Style.RESET_ALL}")
            rag_system = RAGSystem(cfg)

            if clear_cache:
                print(f"{Fore.YELLOW}  Clearing ChromaDB cache...{Style.RESET_ALL}")
                rag_system.clear_collection()

            rag_system.index_chunks(chunks)
            print(f"{Fore.GREEN}✓ RAG system ready{Style.RESET_ALL}\n")

            # Step 3: AI Review
            print(f"{Fore.CYAN}Step 3: Performing AI review...{Style.RESET_ALL}")
            reviewer = AIReviewer(cfg, rag_system)
            ai_results = reviewer.perform_review(files, static_results)
            print(f"\n{Fore.GREEN}✓ AI review complete{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}Error during AI review: {str(e)}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            ai_results = {
                'general_review': 'AI review failed',
                'file_reviews': [],
                'architectural_insights': 'Not available',
                'security_concerns': [],
                'best_practices': [],
                'improvement_suggestions': []
            }
    else:
        print(f"{Fore.YELLOW}Skipping AI review (--no-ai flag){Style.RESET_ALL}")
        ai_results = {
            'general_review': 'AI review skipped',
            'file_reviews': [],
            'architectural_insights': 'Not available',
            'security_concerns': [],
            'best_practices': [],
            'improvement_suggestions': []
        }

    # ==========================
    # Generate Report
    # ==========================
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"GENERATING REPORT")
    print(f"{'='*60}{Style.RESET_ALL}")

    try:
        report_gen = ReportGenerator(cfg)
        report_path = report_gen.generate_report(
            static_results,
            ai_results,
            files,
            path
        )

        print(f"\n{Fore.GREEN}{'='*60}")
        print(f"✓ REVIEW COMPLETE")
        print(f"{'='*60}{Style.RESET_ALL}")
        print(f"\n{Fore.CYAN}Report saved to: {Fore.YELLOW}{report_path}{Style.RESET_ALL}")
        print(f"\n{Fore.WHITE}Open the report in your browser to view detailed results.{Style.RESET_ALL}\n")

    except Exception as e:
        print(f"{Fore.RED}Error generating report: {str(e)}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
