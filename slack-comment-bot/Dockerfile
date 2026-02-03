FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy application files
COPY index.js ./

# Initialize empty comment_store.json if it doesn't exist
RUN echo '{}' > /app/comment_store.json

EXPOSE 3000

CMD ["node", "index.js"]

