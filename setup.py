from setuptools import setup

setup(
    name="stiff",
    version="0.0.2",
    description="Sense Tagged Instances For Finnish",
    url="https://github.com/frankier/stiff/",
    author="Frankie Robertson",
    author_email="frankie@robertson.name",
    license="Apache v2",
    packages=["stiff"],
    install_requires=[
        "click>=6.7",
        "plumbum>=1.6.6",
        "pyahocorasick>=1.1.8",
        "pygtrie>=2.2",
        "opencc>=0.2",
        "opus-api>=0.6.2",
        "finntk>=0.0.24",
        "streamz>=0.3.0",
        "lxml>=4.2.3",
        "conllu>=1.1",
    ],
    extras_require={"dev": ["flake8>=3.5.0", "pre-commit>=1.10.2", "pytest", "mypy"]},
    zip_safe=False,
)
