* Write ~/.pypirc as:

        [distutils]
        index-servers = pypi
        
        [pypi]
        repository :  https://upload.pypi.org/legacy/
        username : <>
        password : <>

* Do:
  
        python3 -m setup sdist
        twine upload dist/*