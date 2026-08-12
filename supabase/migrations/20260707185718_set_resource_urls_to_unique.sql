ALTER TABLE resources
ADD CONSTRAINT unique_portfolio_url UNIQUE (portfolio_url);

ALTER TABLE resources
ADD CONSTRAINT unique_linkedin_url UNIQUE (linked_in_url);