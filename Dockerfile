FROM ubuntu:24.04 AS build

# Install MinGW and build tools
RUN apt-get update && apt-get install -y \
    mingw-w64 \
    make \
    yasm \
    perl \
    python3 \
    git

# For Windows 7/8 compatibility, use these compilers
ENV CC=i686-w64-mingw32-gcc
ENV CXX=i686-w64-mingw32-g++

WORKDIR /app

# Copy only the source code directory
COPY ./src ./src

# Use the proper Makefile build system with cross-compiler, then check the jump table
RUN cd src && make -j"$(nproc)" CC=i686-w64-mingw32-gcc CXX=i686-w64-mingw32-g++ ASM=yasm DLLTOOL=i686-w64-mingw32-dlltool OBJCOPY=i686-w64-mingw32-objcopy \
    && make verify OBJCOPY=i686-w64-mingw32-objcopy

# docker build --output type=local,dest=out .   copies the DLL and its debug symbols into ./out
FROM scratch AS artifacts
COPY --from=build /app/src/ManalinkEh.dll /app/src/ManalinkEh.dbg /
