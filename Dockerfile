# EDeN Docker container
#
# VERSION       0.1.0

FROM ubuntu:14.04

MAINTAINER Björn A. Grüning, bjoern.gruening@gmail.com and Fabrizio Costa

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get -qq update && apt-get install --no-install-recommends -y apt-transport-https \
    python-dev libc-dev python-pip gfortran libfreetype6-dev libpng-dev python-openbabel pkg-config \
    build-essential libblas-dev liblapack-dev git-core wget software-properties-common python-pygraphviz \
    libopenbabel-dev swig libjpeg62-dev && \
    add-apt-repository ppa:bibi-help/bibitools && add-apt-repository ppa:j-4/vienna-rna && \
    apt-get -qq update && \
    apt-get install --no-install-recommends -y rnashapes vienna-rna

# requests: system level package has a bug that makes installing from requirements.txt fail
RUN pip install distribute --upgrade && \
    pip install "requests==2.7.0" >> install.log

# weblogo installation from requirements.txt complains about missing numpy, so install beforehand
RUN pip install "numpy==1.8.0" >> install.log

# scikit-learn installation from requirements.txt complains about missing scipy, so install beforehand
RUN pip install "scipy==0.14.0" >> install.log

# install from local copy of requirements.txt, changes in this file invalidate the cache
ADD requirements.txt .
RUN pip install -r requirements.txt >> install.log

RUN apt-get remove -y --purge libzmq-dev software-properties-common libc-dev libreadline-dev && \
    apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* install.log

RUN mkdir /opt/EDeN
ADD . /opt/EDeN/
ENV PYTHONPATH $PYTHONPATH:/opt/EDeN/
ENV PATH $PATH:/opt/EDeN/bin/
WORKDIR /opt/EDeN
