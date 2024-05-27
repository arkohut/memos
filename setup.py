from setuptools import setup, find_packages

setup(
    name='memos',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'fastapi',
        'uvicorn',
        'httpx',
        'typer'
    ],
    entry_points={
        'console_scripts': [
            'memos=memos.commands:app',
        ],
    },
)
