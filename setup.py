from setuptools import setup, find_packages

setup(
    name="bunnyhopapi",
    version="0.1.0",
    description="Add your description here",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/bunnyhopapi",  # Cambia esto si tienes un repositorio
    packages=find_packages(),
    python_requires=">=3.13",
    install_requires=[
        "pydantic==2.11.0",
        "websockets==15.0.1",
    ],
    extras_require={
        "lint": ["ruff==0.11.2"],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    entry_points={
        "console_scripts": [
            "bunnyhopapi-example=example.main:main",
        ],
    },
)
