from setuptools import setup, find_packages

setup(
    name="agentcorrect",
    version="1.0.0",
    description="Autocorrect for AI Agents - Fix common mistakes automatically",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="AgentCorrect Team",
    url="https://github.com/ishaan-jaff/agentcorrect",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    keywords="ai agents llm autocorrect safety",
    entry_points={
        "console_scripts": [
            "agentcorrect=agentcorrect.cli:main",
        ],
    },
)
