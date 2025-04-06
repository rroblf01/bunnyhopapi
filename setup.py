from setuptools import setup, find_packages

setup(
    name="bunnyhopapi",
    version="1.3.2",
    description="A simple, easy and fast http server for python",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Ricardo Robles Fernández",
    author_email="ricardo.r.f@hotmail.com",
    url="https://github.com/rroblf01/bunnyhopapi",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pydantic==2.11.0",
    ],
    extras_require={
        "lint": ["ruff==0.11.2"],
    },
    license="MIT",
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
