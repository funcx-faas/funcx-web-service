CREATE TABLE requests (
id serial PRIMARY KEY,
user_id varchar(50) NOT NULL,
endpoint varchar(50) NOT NULL,
input_data json NOT NULL,
response_data json,
created_at timestamp default current_timestamp
);

CREATE TABLE tasks(
id serial PRIMARY KEY,
user_id varchar(50) NOT NULL
);

CREATE TABLE sites(
id serial PRIMARY KEY,
user_id integer NOT NULL,
name text NOT NULL,
description text,
created_at timestamp default current_timestamp
)