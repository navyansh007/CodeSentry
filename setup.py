from setuptools import setup, find_packages

setup(
    name="codesentry",
    version="1.0.0",
    description="AI-powered code review system with static analysis and RAG-enhanced LLM review",
    author="CodeSentry Team",
    packages=find_packages(),
    install_requires=[
        line.strip()
        for line in open("requirements.txt").readlines()
        if line.strip() and not line.startswith("#")
    ],
    entry_points={
        "console_scripts": [
            "codesentry=codesentry.cli:main",
            "codesentry-pr=codesentry.github_cli:main",
        ],
    },
    python_requires=">=3.8",
)
