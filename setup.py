"""Setup configuration for AgentCorrect."""

from setuptools import setup, find_packages
import os

# Read version from __init__.py
here = os.path.abspath(os.path.dirname(__file__))
version = "0.1.0"  # Default version
try:
    with open(os.path.join(here, 'agentcorrect', '__init__.py'), 'r') as f:
        for line in f:
            if line.startswith('__version__'):
                version = line.split('"')[1]
                break
except:
    pass

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="agentcorrect",
    version=version,
    author="AgentCorrect Team",
    author_email="support@agentcorrect.com",
    description="CI/CD guardrails for AI agents - prevent payment duplicates and data destruction",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/agentcorrect",
    project_urls={
        "Bug Tracker": "https://github.com/yourusername/agentcorrect/issues",
        "Documentation": "https://docs.agentcorrect.com",
        "Source Code": "https://github.com/yourusername/agentcorrect",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "sqlparse>=0.4.0",
        "tldextract>=3.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "mypy>=0.950",
            "build>=0.7.0",
            "twine>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "agentcorrect=agentcorrect.cli:main",
        ],
    },
    include_package_data=True,
    keywords="ai agent safety cicd testing payment sql security",
)