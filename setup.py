import setuptools

setuptools.setup(
    name="LuaStakky",
    version="0.1.0",
    author="Artem3213212",
    author_email="artem@agteam.dev",
    description="Full stack lua web framework",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/LuaStakky/LuaStakky",
    install_requires=[
        'luaparser>=3.0.0',
        'gitignore-parser>=0.0.8',
        'HiYaPyCo>=0.4.16',
        'docker-compose>=1.28.5'
    ],
    project_urls={
        "Bug Tracker": "https://github.com/LuaStakky/LuaStakky/issues",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Other",
        "Topic :: Internet :: WWW/HTTP :: Site Management",
        "Topic :: Software Development",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Application Frameworks"
    ],
    entry_points={
        'console_scripts': [
            'stakky=LuaStakky',
        ],
    },
    package_data={
        "": ["default.yaml"]
    },
    packages=setuptools.find_packages(),
    python_requires=">=3.6"
)
