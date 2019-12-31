from setuptools import setup

with open('README.md', 'r') as readme:
    long = readme.read()

version = '0.0.3'
name = 'dispatch'
url = f'https://github.com/harrybrwn/{name}'

setup(
   name=f'py-{name}',
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
        "Programming Language :: Python :: 3.7",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
)
