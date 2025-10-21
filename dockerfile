# -----------------------------
# Dockerfile for Django + PostGIS
# -----------------------------
FROM python:3.10-slim

# ติดตั้ง dependencies พื้นฐาน
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    libproj-dev \
    libpq-dev \
    build-essential \
    python3-dev \
    unzip \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV GDAL_LIBRARY_PATH=/usr/lib/libgdal.so
ENV PROJ_LIB=/usr/share/proj

# ตั้ง working directory
WORKDIR /app

# คัดลอก requirements.txt
COPY requirements.txt .

# ติดตั้ง Python packages
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# คัดลอกโปรเจกต์ทั้งหมด
COPY . .

# เปิดพอร์ต Django
EXPOSE 8000

# คำสั่งเริ่มต้นรัน Django server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]