from setuptools import setup

setup(
    name='yosun',
    version='0.1.0',
    description='Simple pub/sub client on top of Kombu',
    author='Yigit Ozen',
    author_email='ozen@computer.org',
    url='http://ozen.github.io',
    py_modules=['yosun'],
    install_requires=['kombu'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Communications',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
)
