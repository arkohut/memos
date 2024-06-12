from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()
long_description = (here / 'README.md').read_text(encoding='utf-8')

setup(
    name='memos',
    version='0.1.0',
    packages=find_packages(),
    long_description=long_description,
    long_description_content_type='text/markdown',
    author="arkohut",
    url="https://github.com/arkohut/memos",
    install_requires=[
        'fastapi',
        'uvicorn',
        'httpx',
        'pydantic',
        'sqlalchemy',
        'typer',
        'magika'
    ],
    entry_points={
        'console_scripts': [
            'memos=memos.commands:app',
        ],
    },
    python_requires='>=3.10',
)
