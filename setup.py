"""Cython build file"""
if __name__ == '__main__':
    from distutils.core import setup
    from distutils.extension import Extension
    from Cython.Build import cythonize
    from Cython.Distutils import build_ext
    import os

    cythonExt = []
    for root, dirs, files in os.walk(os.getcwd()):
        for file in files:
            if file.endswith(".pyx") and ".pyenv" not in root:  # im sorry
                filePath = os.path.relpath(os.path.join(root, file))
                cythonExt.append(Extension(filePath.replace(os.path.sep, ".")[:-4], [filePath], language='c++'))

    setup(
        name="pep.pyx modules",
        ext_modules=cythonize(cythonExt, nthreads=4),
        cmdclass={'build_ext': build_ext},
    )
