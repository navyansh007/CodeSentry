"""
AI Review Layer - LLM-powered code review against any configured provider
"""

import os
from typing import List, Dict, Any, Optional
from .rag_system import RAGSystem
from .llm_providers import create_provider, LLMProviderError


class AIReviewer:
    """AI-powered code reviewer using a configurable LLM provider with RAG"""

    SYSTEM_PROMPT = (
        "You are an expert code reviewer with deep knowledge of software "
        "engineering best practices, security, and performance optimization."
    )

    def __init__(self, config: Dict[str, Any], rag_system: RAGSystem):
        self.config = config
        self.rag_system = rag_system

        try:
            self.provider = create_provider(config)
        except LLMProviderError as e:
            print(f"Warning: {str(e)}")
            self.provider = None

        if self.provider and not self.provider.is_configured():
            print(f"Warning: {self.provider.missing_key_message()}")

        self.review_results = {
            'general_review': '',
            'file_reviews': [],
            'architectural_insights': '',
            'security_concerns': [],
            'best_practices': [],
            'improvement_suggestions': []
        }

    def perform_review(self, files: List[str], static_results: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive AI-powered code review"""
        print("\nPerforming AI-powered code review...")

        # 1. General codebase overview
        print("  Generating general codebase review...")
        self.review_results['general_review'] = self._review_general_codebase()

        # 2. Architectural analysis
        print("  Analyzing architecture...")
        self.review_results['architectural_insights'] = self._analyze_architecture(files)

        # 3. Security analysis
        print("  Analyzing security concerns...")
        self.review_results['security_concerns'] = self._analyze_security(static_results)

        # 4. File-specific reviews (sample of files)
        print("  Reviewing individual files...")
        self.review_results['file_reviews'] = self._review_files(files[:5])  # Review first 5 files

        # 5. Best practices check
        print("  Checking best practices...")
        self.review_results['best_practices'] = self._check_best_practices()

        # 6. Generate improvement suggestions
        print("  Generating improvement suggestions...")
        self.review_results['improvement_suggestions'] = self._generate_suggestions(static_results)

        return self.review_results

    def _review_general_codebase(self) -> str:
        """Generate general codebase review"""
        # Get diverse code samples
        samples = self.rag_system.get_diverse_samples(n_samples=8)

        if not samples:
            return "Unable to generate review: no code samples available"

        # Build context
        context = self._build_context_from_samples(samples)

        # Create prompt
        prompt = f"""You are an expert code reviewer. Analyze the following codebase samples and provide a comprehensive overview.

Context from codebase:
{context}

Please provide:
1. Overall code quality assessment
2. Code organization and structure
3. Notable patterns or anti-patterns
4. General observations

Keep your response concise and actionable."""

        return self._call_llm(prompt)

    def _analyze_architecture(self, files: List[str]) -> str:
        """Analyze codebase architecture"""
        # Get structural information
        file_structure = self._analyze_file_structure(files)

        prompt = f"""Analyze the architecture of this codebase based on the following file structure:

{file_structure}

Provide insights on:
1. Project organization and modularity
2. Separation of concerns
3. Potential architectural improvements
4. Scalability considerations

Be specific and actionable."""

        return self._call_llm(prompt)

    def _analyze_security(self, static_results: Dict[str, Any]) -> List[str]:
        """Analyze security concerns"""
        concerns = []

        # Get security issues from static analysis
        bandit_issues = static_results.get('bandit', [])

        if bandit_issues:
            # Get relevant code context for security issues
            for issue in bandit_issues[:5]:  # Analyze top 5 security issues
                file_path = issue.get('filename', '')
                line_num = issue.get('line_number', 0)
                issue_text = issue.get('issue_text', '')

                # Retrieve context from RAG
                context_chunks = self.rag_system.retrieve_file_context(file_path)

                if context_chunks:
                    context = context_chunks[0]['content']

                    prompt = f"""Analyze this security issue:

Issue: {issue_text}
File: {file_path}
Line: {line_num}

Code context:
{context[:500]}

Provide:
1. Severity assessment
2. Potential impact
3. Recommended fix
4. Prevention strategy

Be concise."""

                    analysis = self._call_llm(prompt)
                    concerns.append({
                        'issue': issue_text,
                        'file': file_path,
                        'line': line_num,
                        'analysis': analysis
                    })

        return concerns

    def _review_files(self, files: List[str]) -> List[Dict[str, Any]]:
        """Review individual files"""
        reviews = []

        for file_path in files:
            # Get file context from RAG
            context_chunks = self.rag_system.retrieve_file_context(file_path)

            if not context_chunks:
                continue

            # Combine chunks
            file_content = '\n\n'.join([chunk['content'] for chunk in context_chunks[:3]])

            prompt = f"""Review the following code file:

File: {file_path}

Code:
{file_content[:2000]}

Provide a focused review covering:
1. Code quality and readability
2. Potential bugs or issues
3. Performance considerations
4. Specific improvement suggestions

Be concise and practical."""

            review = self._call_llm(prompt)

            reviews.append({
                'file': file_path,
                'review': review
            })

        return reviews

    def _check_best_practices(self) -> List[str]:
        """Check for best practices"""
        samples = self.rag_system.get_diverse_samples(n_samples=5)

        if not samples:
            return []

        context = self._build_context_from_samples(samples)

        prompt = f"""Analyze these code samples for adherence to best practices:

{context}

Identify:
1. Violations of coding best practices
2. Missing documentation or comments
3. Naming convention issues
4. Code duplication
5. Error handling gaps

Provide specific examples with line references when possible."""

        response = self._call_llm(prompt)

        # Split response into list items
        practices = [item.strip() for item in response.split('\n') if item.strip()]
        return practices

    def _generate_suggestions(self, static_results: Dict[str, Any]) -> List[str]:
        """Generate improvement suggestions based on static analysis"""
        suggestions = []

        summary = static_results.get('summary', {})

        prompt = f"""Based on static analysis results, provide improvement suggestions:

Static Analysis Summary:
- Total Issues: {summary.get('total_issues', 0)}
- Pylint Issues: {summary.get('pylint_issues', 0)}
- Flake8 Issues: {summary.get('flake8_issues', 0)}
- Security Issues: {summary.get('bandit_issues', 0)}
- High Complexity Functions: {summary.get('high_complexity_functions', 0)}

Severity Breakdown:
- Errors: {summary.get('severity_breakdown', {}).get('error', 0)}
- Warnings: {summary.get('severity_breakdown', {}).get('warning', 0)}
- Security: {summary.get('severity_breakdown', {}).get('security', 0)}

Provide 5-7 prioritized improvement suggestions for this codebase."""

        response = self._call_llm(prompt)

        # Split into list
        suggestions = [item.strip() for item in response.split('\n') if item.strip() and len(item.strip()) > 10]
        return suggestions[:7]

    def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM provider"""
        if not self.provider:
            return "Error: no LLM provider configured"
        if not self.provider.is_configured():
            return f"Error: {self.provider.missing_key_message()}"

        try:
            return self.provider.chat(prompt, self.SYSTEM_PROMPT)
        except Exception as e:
            return f"Error: {str(e)}"

    def _build_context_from_samples(self, samples: List[Dict[str, Any]]) -> str:
        """Build context string from code samples"""
        context_parts = []

        for sample in samples:
            metadata = sample['metadata']
            content = sample['content']

            context_parts.append(f"""
File: {metadata['file_path']}
Lines: {metadata['start_line']}-{metadata['end_line']}

```
{content[:800]}
```
""")

        return '\n'.join(context_parts)

    def _analyze_file_structure(self, files: List[str]) -> str:
        """Analyze and format file structure"""
        # Group files by directory
        structure = {}

        for file_path in files:
            parts = file_path.split(os.sep)
            if len(parts) > 1:
                directory = os.sep.join(parts[:-1])
                filename = parts[-1]

                if directory not in structure:
                    structure[directory] = []
                structure[directory].append(filename)

        # Format structure
        formatted = []
        for directory, filenames in sorted(structure.items()):
            formatted.append(f"\n{directory}/")
            for filename in sorted(filenames):
                formatted.append(f"  - {filename}")

        return '\n'.join(formatted)
