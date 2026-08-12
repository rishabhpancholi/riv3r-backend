ALTER TABLE organizations 
ADD CONSTRAINT unique_website_url UNIQUE (website_url);