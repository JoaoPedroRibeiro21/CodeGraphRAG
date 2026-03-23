CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
    "id" UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "identifier" TEXT NOT NULL UNIQUE,
    "metadata" JSONB NOT NULL,
    "createdAt" TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS threads (
    "id" UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "createdAt" TEXT NOT NULL,
    "name" TEXT,
    "userId" UUID,
    "userIdentifier" TEXT,
    "tags" TEXT[],
    "metadata" JSONB,
    FOREIGN KEY ("userId") REFERENCES users("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS steps (
    "id" UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "name" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "threadId" UUID NOT NULL,
    "parentId" UUID,
    "streaming" BOOLEAN NOT NULL,
    "waitForAnswer" BOOLEAN,
    "isError" BOOLEAN,
    "metadata" JSONB,
    "tags" TEXT[],
    "input" TEXT,
    "output" TEXT,
    "createdAt" TEXT,
    "start" TEXT,
    "end" TEXT,
    "generation" JSONB,
    "showInput" TEXT,
    "language" TEXT,
    "indent" INT,
    "modes" TEXT[]
);

CREATE TABLE IF NOT EXISTS elements (
    "id" UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "threadId" UUID,
    "type" TEXT,
    "url" TEXT,
    "chainlitKey" TEXT,
    "name" TEXT NOT NULL,
    "display" TEXT,
    "objectKey" TEXT,
    "size" TEXT,
    "page" INT,
    "language" TEXT,
    "forId" UUID,
    "mime" TEXT
);

CREATE TABLE IF NOT EXISTS feedbacks (
    "id" UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "forId" UUID NOT NULL,
    "value" INT NOT NULL,
    "comment" TEXT
);
