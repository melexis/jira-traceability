# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

project_url = 'https://github.com/melexis/jira-traceability'

requires = ['Sphinx>=2.1', 'jira', 'mlx.traceability>=9.0.0']

setup(
    name='mlx.jira-traceability',
    use_scm_version={
        'write_to': 'mlx/__version__.py'
    },
    setup_requires=['setuptools_scm'],
    url=project_url,
    license='Apache License, Version 2.0',
    author='Jasper Craeghs',
    author_email='jce@melexis.com',
    description='Sphinx plugin to create Jira tickets based on traceable items',
    long_description=open("README.rst").read(),
    long_description_content_type='text/x-rst',
    zip_safe=False,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Framework :: Sphinx :: Extension',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Documentation :: Sphinx',
        'Topic :: Software Development :: Bug Tracking',
        'Topic :: Utilities',
    ],
    platforms='any',
    packages=find_packages(exclude=['tests', 'doc']),
    include_package_data=True,
    install_requires=requires,
    python_requires='>=3.7',
    namespace_packages=['mlx'],
    keywords=[
        'traceability',
        'jira',
        'sphinx',
    ],
)
