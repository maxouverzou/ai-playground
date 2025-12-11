FROM node:lts-alpine

# Install dependencies globally
RUN npm install -g @modelcontextprotocol/server-github supergateway

# Expose the port
EXPOSE 8000

# Run supergateway
CMD supergateway --port 8000 --stdio "npx -y @modelcontextprotocol/server-github"
