FROM node:22-alpine

WORKDIR /app

COPY package.json ./
# Run npm install with legacy peer deps for modern react 19 compatibility
RUN npm install --legacy-peer-deps

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
