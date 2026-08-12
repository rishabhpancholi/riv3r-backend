ALTER TABLE refresh_tokens
ADD CONSTRAINT refresh_tokens_refresh_token_key UNIQUE (refresh_token);