from setuptools import setup

with open('README.md', 'r') as readme:
    long = readme.read()

setup(
   name='dispatch',
   version='0.0.1',
   description='A low information-redundancy cli framework.',
   long_description=long,
   author='Harrison Brown',
   author_email='harrybrown98@gmail.com',
   packages=['dispatch'],
)