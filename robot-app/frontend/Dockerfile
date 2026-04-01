FROM node:18-slim

WORKDIR /app

# Copy frontend files
COPY . .

# Expose port
EXPOSE 3000

# Serve the frontend with a simple HTTP server
RUN npm install -g http-server

CMD ["http-server", "-p", "3000", "-c-1"]
