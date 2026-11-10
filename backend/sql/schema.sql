CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE TABLE IF NOT EXISTS person (
  id INT PRIMARY KEY,                 -- TMDB id
  name TEXT NOT NULL,
  name_search TEXT NOT NULL,          -- lowercased, accents removed
  profile_path TEXT,
  total_votes INT NOT NULL DEFAULT 0,
  endpoint_eligible BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS movie (
  id INT PRIMARY KEY,                 -- TMDB id
  title TEXT NOT NULL,
  title_search TEXT NOT NULL,
  release_year SMALLINT NOT NULL,
  runtime SMALLINT NOT NULL,
  genres SMALLINT[] NOT NULL,
  original_language TEXT,
  poster_path TEXT,
  vote_count INT NOT NULL,
  obscurity REAL NOT NULL,            -- 0 to 1
  tier SMALLINT NOT NULL              -- 1 to 3
);

CREATE TABLE IF NOT EXISTS credit (
  movie_id INT REFERENCES movie(id),
  person_id INT REFERENCES person(id),
  billing_order SMALLINT NOT NULL,    -- 0 to 14
  PRIMARY KEY (movie_id, person_id)
);
CREATE INDEX IF NOT EXISTS credit_person_idx ON credit (person_id, movie_id);

CREATE TABLE IF NOT EXISTS puzzle (
  number INT PRIMARY KEY,
  play_date DATE UNIQUE NOT NULL,
  start_person_id INT NOT NULL REFERENCES person(id),
  end_person_id INT NOT NULL REFERENCES person(id),
  par SMALLINT NOT NULL,
  example_route JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS movie_title_trgm ON movie USING GIN (title_search gin_trgm_ops);
CREATE INDEX IF NOT EXISTS person_name_trgm ON person USING GIN (name_search gin_trgm_ops);
