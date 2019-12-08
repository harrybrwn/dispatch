from setuptools import setup

with open('README.md', 'r') as readme:
    long = readme.read()

version = '0.0.1'
name = 'dispatch'
url = f'https://github.com/harrybrwn/{name}'

setup(
   name=name,
   version=version,
   author='Harrison Brown',
   author_email='harrybrown98@gmail.com',
   license='Apache 2.0',
   packages=[name],
   description='A low information-redundancy cli framework.',
   long_description=long,
   long_description_content_type="text/markdown",
   url=url,
   download_url=f'{url}/archive/v{version}.tar.gz',
   keywords=['command line', 'cli', 'framework', 'tool', 'simple'],
   install_requires=['jinja2'],
   classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache License 2.0",
        "Operating System :: OS Independent",
    ],
)
