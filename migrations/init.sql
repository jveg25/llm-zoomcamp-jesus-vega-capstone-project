-- pgvector: adds the `vector` column type + similarity operators
CREATE EXTENSION IF NOT EXISTS vector;

-- ============ Knowledge base ============

CREATE TABLE papers (
    id          serial PRIMARY KEY,
    filename    text UNIQUE NOT NULL,   -- idempotency key: re-running ingestion skips existing
    title       text NOT NULL,
    authors     text,
    year        int,
    summary     text,                   -- LLM-generated at ingestion
    source_url  text,                   -- for dataset accessibility + citations
    ingested_at timestamptz DEFAULT now()
);

CREATE TABLE chunks (
    id          serial PRIMARY KEY,
    paper_id    int NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    chunk_index int NOT NULL,
    section     text,                   -- heading the chunk came from (citations)
    page_start  int,
    page_end    int,
    kind        text NOT NULL DEFAULT 'text',  -- 'text' | 'figure' | 'summary' | 'qa'
    content     text NOT NULL,
    embedding   vector(1536),           -- MUST match text-embedding-3-small dims
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

-- Vector search index: HNSW, cosine distance (what OpenAI embeddings expect)
CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
-- Keyword search index: GIN over the generated tsvector
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);

-- ============ Users & access ============

CREATE TABLE profiles (
    user_id    uuid PRIMARY KEY,        -- will FK to auth.users when GoTrue is wired in
    email      text,
    role       text NOT NULL DEFAULT 'pending'
               CHECK (role IN ('pending', 'user', 'admin')),
    created_at timestamptz DEFAULT now()
);

-- ============ Conversations, feedback, monitoring ============

CREATE TABLE conversations (
    id                 serial PRIMARY KEY,
    user_id            uuid REFERENCES profiles(user_id),
    question           text NOT NULL,
    rewritten_question text,            -- observability: did rewriting help or hurt?
    answer             text,
    model              text,
    prompt_tokens      int,
    completion_tokens  int,
    cost_usd           numeric(10,6),
    response_time_ms   int,
    retrieval_score    real,            -- top hit score; feeds "unknown answer" detection
    answer_found       boolean,         -- structured flag from the LLM, not parsed prose
    created_at         timestamptz DEFAULT now()
);

CREATE TABLE feedback (
    id              serial PRIMARY KEY,
    conversation_id int NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id         uuid REFERENCES profiles(user_id),
    value           smallint NOT NULL CHECK (value IN (-1, 1)),  -- 👎 / 👍
    created_at      timestamptz DEFAULT now()
);

-- ============ Human-in-the-loop queue ============

CREATE TABLE unanswered_questions (
    id              serial PRIMARY KEY,
    conversation_id int REFERENCES conversations(id),
    question        text NOT NULL,
    status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'answered', 'integrated')),
    human_answer    text,
    answered_by     uuid REFERENCES profiles(user_id),
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);