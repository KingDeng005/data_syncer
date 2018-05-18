import os
from setuptools import setup, find_packages

setup(
    name='data-syncer',
    packages=find_packages(),
    entry_points={
        "console_scripts": ['data-syncer = data_syncer.data_syncer:main']
    },
    version='0.0.5',
    author='Fuheng Deng',
    author_email='fuheng.deng@tusimple.ai',
    description=('data syncer tool for tusimple data transmission pipeline.'),
    license='BSD'
)
