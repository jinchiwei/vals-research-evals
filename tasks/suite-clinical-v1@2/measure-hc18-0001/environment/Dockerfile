FROM python:3.12-slim
# Every Python dependency lives in one virtualenv inside the image; nothing in system Python.
# Packages are this family's own declaration (measure_hc18).
RUN python3 -m venv /opt/benchmark-venv && /opt/benchmark-venv/bin/python -m pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 nibabel==5.3.2 SimpleITK==2.4.0 scikit-image==0.24.0 scikit-learn==1.5.2 pillow==11.0.0 pandas==2.2.3
ENV PATH=/opt/benchmark-venv/bin:$PATH VIRTUAL_ENV=/opt/benchmark-venv PYTHONDONTWRITEBYTECODE=1 PIP_NO_INDEX=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 \
    MKL_NUM_THREADS=4 ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=4
# Fail the build (closed) if the declared runtime is incomplete.
RUN python3 -c "import sys; assert sys.prefix == '/opt/benchmark-venv', sys.prefix; import numpy, scipy, nibabel, SimpleITK, skimage, sklearn, PIL, pandas"
# Login shells source /etc/profile, which resets PATH on Debian; put the venv first there too,
# then fail the build unless every shell (login or not, with or without the image ENV) finds it.
RUN echo 'export PATH="/opt/benchmark-venv/bin:$PATH" VIRTUAL_ENV=/opt/benchmark-venv' > /etc/profile.d/00-benchmark-venv.sh && chmod 0644 /etc/profile.d/00-benchmark-venv.sh
RUN for s in 'bash -lc' 'bash -c' 'sh -lc' 'sh -c' 'env -i bash -lc' 'env -i sh -lc'; do p="$($s 'command -v python3')"; [ "$p" = /opt/benchmark-venv/bin/python3 ] || { echo "$s resolves python3 to $p" >&2; exit 1; }; done
WORKDIR /workspace
COPY data/ /workspace/data/
RUN chmod -R a-w /workspace/data && mkdir -p /workspace/output && chmod 0777 /workspace/output
