#########################################################################################
##  Stage 2: build DALI wheels on top of the dependencies image built in Stage 1
#########################################################################################
ARG DEPS_IMAGE_NAME
# clean builder without source code inside
FROM ${DEPS_IMAGE_NAME} as builder

ARG PYVER=3.6
ARG PYV=36

ENV PYVER=${PYVER} PYV=${PYV} PYTHONPATH=/opt/python/v

ENV PYBIN=${PYTHONPATH}/bin \
    PYLIB=${PYTHONPATH}/lib

# add llvm-toolset-7.0 for python clang bindings on aarch64 where libclang wheel is not available
ENV PATH=/opt/python/cp36-cp36/bin:/opt/python/cp37-cp37m/bin:/opt/python/cp38-cp38/bin:/opt/python/cp39-cp39/bin:/usr/local/cuda/bin:${PYBIN}:${PATH} \
    LD_LIBRARY_PATH=/opt/rh/llvm-toolset-7.0/root/usr/lib64:/usr/local/cuda/lib64/stubs:/opt/dali/${DALI_BUILD_DIR}:/opt/python/cp36-cp36/lib:/opt/python/cp37-cp37m/lib:/opt/python/cp38-cp38/lib:/opt/python/cp39-cp39/lib:${PYLIB}:${LD_LIBRARY_PATH} \
    LIBRARY_PATH=/opt/rh/llvm-toolset-7.0/root/usr/lib64:/usr/local/cuda/lib64/stubs:/opt/dali/${DALI_BUILD_DIR}:/opt/python/cp36-cp36/lib:/opt/python/cp37-cp37m/lib:/opt/python/cp38-cp38/lib:/opt/python/cp39-cp39/lib:${PYLIB}:${LIBRARY_PATH}

RUN ln -s /opt/python/cp${PYV}* /opt/python/v

# in aarch64 pip install libclang will fail
RUN pip install future setuptools wheel clang && \
    pip install libclang || true && \
    rm -rf /root/.cache/pip/

# install clang for aarch64 from llvm-toolset-7.0, and patch clang pip package to use it
RUN if [ "$(uname -m)" == "aarch64" ]; then \
        yum install -y centos-release-scl && \
        yum-config-manager -y --enable rhel-server-rhscl-7-rpms && \
        yum install -y llvm-toolset-7.0 && \
        PY_CLANG_PATH=$(echo $(pip show clang) | sed 's/.*Location: \(.*\) Requires.*/\1/')/clang/cindex.py && \
        sed -i 's/library_file = None/library_file = "\/opt\/rh\/llvm-toolset-7.0\/root\/usr\/lib64\/libclang.so.7"/' ${PY_CLANG_PATH}; \
    fi

RUN ln -s /usr/local/cuda/lib64/stubs/libcuda.so /usr/local/cuda/lib64/stubs/libcuda.so.1 && \
    ldconfig

WORKDIR /opt/dali

ARG CC
ARG CXX
ENV CC=${CC}
ENV CXX=${CXX}
# Optional build arguments

ARG ARCH
ENV ARCH=${ARCH}
ARG CUDA_TARGET_ARCHS
ENV CUDA_TARGET_ARCHS=${CUDA_TARGET_ARCHS}
ARG CMAKE_BUILD_TYPE
ENV CMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}
ARG BUILD_TEST
ENV BUILD_TEST=${BUILD_TEST}
ARG BUILD_BENCHMARK
ENV BUILD_BENCHMARK=${BUILD_BENCHMARK}
ARG BUILD_NVTX
ENV BUILD_NVTX=${BUILD_NVTX}
ARG BUILD_PYTHON
ENV BUILD_PYTHON=${BUILD_PYTHON}
ARG BUILD_LMDB
ENV BUILD_LMDB=${BUILD_LMDB}
ARG BUILD_JPEG_TURBO
ENV BUILD_JPEG_TURBO=${BUILD_JPEG_TURBO}
ARG BUILD_NVJPEG
ENV BUILD_NVJPEG=${BUILD_NVJPEG}
ARG BUILD_NVJPEG2K
ENV BUILD_NVJPEG2K=${BUILD_NVJPEG2K}
ARG BUILD_LIBTIFF
ENV BUILD_LIBTIFF=${BUILD_LIBTIFF}
ARG BUILD_LIBSND
ENV BUILD_LIBSND=${BUILD_LIBSND}
ARG BUILD_FFTS
ENV BUILD_FFTS=${BUILD_FFTS}
ARG BUILD_NVOF
ENV BUILD_NVOF=${BUILD_NVOF}
ARG BUILD_NVDEC
ENV BUILD_NVDEC=${BUILD_NVDEC}
ARG BUILD_NVML
ENV BUILD_NVML=${BUILD_NVML}
ARG BUILD_CUFILE
ENV BUILD_CUFILE=${BUILD_CUFILE}
ARG LINK_DRIVER
ENV LINK_DRIVER=${LINK_DRIVER}
ARG STRIP_BINARY
ENV STRIP_BINARY=${STRIP_BINARY}
ARG VERBOSE_LOGS
ENV VERBOSE_LOGS=${VERBOSE_LOGS}
ARG NVIDIA_DALI_BUILD_FLAVOR
ENV NVIDIA_DALI_BUILD_FLAVOR=${NVIDIA_DALI_BUILD_FLAVOR}
ARG GIT_SHA
ENV GIT_SHA=${GIT_SHA}
ARG DALI_TIMESTAMP
ENV DALI_TIMESTAMP=${DALI_TIMESTAMP}
ARG WHL_PLATFORM_NAME
ENV WHL_PLATFORM_NAME=${WHL_PLATFORM_NAME}
ARG EXTRA_CMAKE_OPTIONS
ENV EXTRA_CMAKE_OPTIONS=${EXTRA_CMAKE_OPTIONS}

ARG NVIDIA_BUILD_ID
ENV NVIDIA_BUILD_ID ${NVIDIA_BUILD_ID:-0}
RUN mkdir /wheelhouse && chmod 0777 /wheelhouse

FROM builder
COPY . .

ARG DALI_BUILD_DIR=build-docker-release
WORKDIR /opt/dali/${DALI_BUILD_DIR}

RUN bash /opt/dali/docker/build_helper.sh
