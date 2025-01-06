FROM python:3.9

WORKDIR /app

# Copy requirements first for better caching
COPY ./requirements.txt /app/
COPY ./src/ /app/src/

RUN pip install --no-cache-dir -r requirements.txt

# Expose the port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
