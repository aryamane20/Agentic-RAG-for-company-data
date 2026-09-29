-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create roles table
CREATE TABLE roles (
  id SERIAL PRIMARY KEY,
  name VARCHAR(50) UNIQUE NOT NULL
);

-- Seed roles table
INSERT INTO roles (name) VALUES
  ('hr_staff'),
  ('engineer'),
  ('executive');

-- Create users table
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  role_id INTEGER NOT NULL REFERENCES roles(id),
  password_hash TEXT
);

-- Create documents table
CREATE TABLE documents (
  id SERIAL PRIMARY KEY,
  filename VARCHAR(255) NOT NULL UNIQUE,
  department VARCHAR(100) NOT NULL
);

-- Create document_roles table (permission policy)
CREATE TABLE document_roles (
  id SERIAL PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  UNIQUE(document_id, role_id)
);

-- Create chunks table
CREATE TABLE chunks (
  id SERIAL PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  embedding vector(384)
);

-- Create HNSW index on embedding column for cosine distance
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);

-- Create index on document_roles by role_id
CREATE INDEX idx_document_roles_role_id ON document_roles(role_id);

-- Create conversations table
CREATE TABLE conversations (
  id UUID PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_conversations_user_updated ON conversations(user_id, updated_at DESC);

-- Create messages table
CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  source_documents TEXT[] NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_messages_conversation_created ON messages(conversation_id, created_at);
