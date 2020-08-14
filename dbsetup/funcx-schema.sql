--
-- PostgreSQL database dump
--

-- Dumped from database version 10.6
-- Dumped by pg_dump version 12.3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

--
-- Name: action_instance; Type: TABLE; Schema: public; Owner: funcx
--

CREATE TABLE public.action_instance (
    action_id character varying NOT NULL,
    request_id character varying NOT NULL,
    request_body jsonb NOT NULL,
    creator_id character varying NOT NULL,
    label character varying(64),
    monitor_by character varying[],
    manage_by character varying[],
    allowed_clients character varying[],
    start_time timestamp without time zone NOT NULL,
    completion_time timestamp without time zone,
    release_after character varying NOT NULL,
    release_time timestamp without time zone,
    status character varying NOT NULL,
    display_status character varying(64),
    details jsonb,
    provider_private jsonb
);


ALTER TABLE public.action_instance OWNER TO funcx;

--
-- Name: auth_groups; Type: TABLE; Schema: public; Owner: funcx
--

CREATE TABLE public.auth_groups (
    id bigint NOT NULL,
    group_id text,
    endpoint_id text
);


ALTER TABLE public.auth_groups OWNER TO funcx;

--
-- Name: auth_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: funcx
--

CREATE SEQUENCE public.auth_groups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.auth_groups_id_seq OWNER TO funcx;

--
-- Name: auth_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: funcx
--

ALTER SEQUENCE public.auth_groups_id_seq OWNED BY public.auth_groups.id;


--
-- Name: container_images; Type: TABLE; Schema: public; Owner: funcx
--

CREATE TABLE public.container_images (
    id bigint NOT NULL,
    container_id integer,
    type text,
    location text,
    created_at timestamp without time zone DEFAULT now(),
    modified_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.container_images OWNER TO funcx;

--
-- Name: container_images_id_seq; Type: SEQUENCE; Schema: public; Owner: funcx
--

CREATE SEQUENCE public.container_images_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.container_images_id_seq OWNER TO funcx;

--
-- Name: container_images_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: funcx
--

ALTER SEQUENCE public.container_images_id_seq OWNED BY public.container_images.id;


--
-- Name: containers; Type: TABLE; Schema: public; Owner: funcx
--

CREATE TABLE public.containers (
    id bigint NOT NULL,
    author integer,
    container_uuid text,
    description text,
    created_at timestamp without time zone DEFAULT now(),
    modified_at timestamp without time zone DEFAULT now(),
    name text
);


ALTER TABLE public.containers OWNER TO funcx;

--
-- Name: containers_id_seq; Type: SEQUENCE; Schema: public; Owner: funcx
--

CREATE SEQUENCE public.containers_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.containers_id_seq OWNER TO funcx;

--
-- Name: containers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: funcx
--

ALTER SEQUENCE public.containers_id_seq OWNED BY public.containers.id;


--
-- Name: function_auth_groups; Type: TABLE; Schema: public; Owner: funcx
--

CREATE TABLE public.function_auth_groups (
    id bigint NOT NULL,
    group_id text,
    function_id text
);


ALTER TABLE public.function_auth_groups OWNER TO funcx;

--
-- Name: function_auth_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: funcx
--

CREATE SEQUENCE public.function_auth_groups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.function_auth_groups_id_seq OWNER TO funcx;

--
-- Name: function_auth_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: funcx
--

ALTER SEQUENCE public.function_auth_groups_id_seq OWNED BY public.function_auth_groups.id;


--
-- Name: function_containers; Type: TABLE; Schema: public; Owner: funcx
--

CREATE TABLE public.function_containers (
    id bigint NOT NULL,
    container_id integer,
    function_id integer,
    created_at timestamp without time zone DEFAULT now(),
    modified_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.function_containers OWNER TO funcx;

--
-- Name: function_containers_id_seq; Type: SEQUENCE; Schema: public; Owner: funcx
--

CREATE SEQUENCE public.function_containers_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.function_containers_id_seq OWNER TO funcx;

--
-- Name: function_containers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: funcx
--

ALTER SEQUENCE public.function_containers_id_seq OWNED BY public.function_containers.id;


--
-- Name: functions; Type: TABLE; Schema: public; Owner: funcx
--

CREATE TABLE public.functions (
    id bigint NOT NULL,
    user_id integer,
    name text,
    description text,
    status text,
    function_name text,
    function_uuid text,
    function_code text,
    "timestamp" timestamp without time zone DEFAULT now(),
    entry_point text,
    modified_at timestamp without time zone DEFAULT now(),
    deleted boolean DEFAULT false,
    public boolean DEFAULT false
);


ALTER TABLE public.functions OWNER TO funcx;

--
-- Name: functions_id_seq; Type: SEQUENCE; Schema: public; Owner: funcx
--

CREATE SEQUENCE public.functions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.functions_id_seq OWNER TO funcx;

--
-- Name: functions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: funcx
--

ALTER SEQUENCE public.functions_id_seq OWNED BY public.functions.id;


--
-- Name: groups; Type: TABLE; Schema: public; Owner: funcx
--

CREATE TABLE public.groups (
    id bigint NOT NULL,
    group_id text,
    priority integer,
    name text,
    description text
);


ALTER TABLE public.groups OWNER TO funcx;

--
-- Name: groups_id_seq; Type: SEQUENCE; Schema: public; Owner: funcx
--

CREATE SEQUENCE public.groups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.groups_id_seq OWNER TO funcx;

--
-- Name: groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: funcx
--

ALTER SEQUENCE public.groups_id_seq OWNED BY public.groups.id;


--
-- Name: requests; Type: TABLE; Schema: public; Owner: funcx
--

CREATE TABLE public.requests (
    id integer NOT NULL,
    user_id character varying(50) NOT NULL,
    endpoint character varying(50) NOT NULL,
    input_data json NOT NULL,
    response_data json,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.requests OWNER TO funcx;

--
-- Name: requests_id_seq; Type: SEQUENCE; Schema: public; Owner: funcx
--

CREATE SEQUENCE public.requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.requests_id_seq OWNER TO funcx;

--
-- Name: requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: funcx
--

ALTER SEQUENCE public.requests_id_seq OWNED BY public.requests.id;


--
-- Name: restricted_endpoint_functions; Type: TABLE; Schema: public; Owner: funcx
--

CREATE TABLE public.restricted_endpoint_functions (
    id bigint NOT NULL,
    endpoint_id text,
    function_id text
);


ALTER TABLE public.restricted_endpoint_functions OWNER TO funcx;

--
-- Name: restricted_endpoint_functions_id_seq; Type: SEQUENCE; Schema: public; Owner: funcx
--

CREATE SEQUENCE public.restricted_endpoint_functions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.restricted_endpoint_functions_id_seq OWNER TO funcx;

--
-- Name: restricted_endpoint_functions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: funcx
--

ALTER SEQUENCE public.restricted_endpoint_functions_id_seq OWNED BY public.restricted_endpoint_functions.id;


--
-- Name: results; Type: TABLE; Schema: public; Owner: funcx
--

CREATE TABLE public.results (
    id bigint NOT NULL,
    task_id text,
    result text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.results OWNER TO funcx;

--
-- Name: results_id_seq; Type: SEQUENCE; Schema: public; Owner: funcx
--

CREATE SEQUENCE public.results_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.results_id_seq OWNER TO funcx;

--
-- Name: results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: funcx
--

ALTER SEQUENCE public.results_id_seq OWNED BY public.results.id;


--
-- Name: sites; Type: TABLE; Schema: public; Owner: funcx
--

CREATE TABLE public.sites (
    id integer NOT NULL,
    user_id integer NOT NULL,
    name text,
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    status text,
    endpoint_name text,
    endpoint_uuid text,
    groups integer[] DEFAULT '{1}'::integer[],
    public boolean DEFAULT false,
    deleted boolean DEFAULT false,
    ip_addr text,
    city text,
    region text,
    country text,
    zipcode text,
    latitude double precision,
    longitude double precision,
    core_hours double precision DEFAULT 0,
    hostname text,
    org text,
    restricted boolean DEFAULT false
);


ALTER TABLE public.sites OWNER TO funcx;

--
-- Name: sites_id_seq; Type: SEQUENCE; Schema: public; Owner: funcx
--

CREATE SEQUENCE public.sites_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.sites_id_seq OWNER TO funcx;

--
-- Name: sites_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: funcx
--

ALTER SEQUENCE public.sites_id_seq OWNED BY public.sites.id;


--
-- Name: tasks; Type: TABLE; Schema: public; Owner: funcx
--

CREATE TABLE public.tasks (
    id integer NOT NULL,
    user_id integer NOT NULL,
    task_id text,
    status character varying(10) DEFAULT 'UNKNOWN'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    modified_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    endpoint_id text,
    function_id text
);


ALTER TABLE public.tasks OWNER TO funcx;

--
-- Name: tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: funcx
--

CREATE SEQUENCE public.tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.tasks_id_seq OWNER TO funcx;

--
-- Name: tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: funcx
--

ALTER SEQUENCE public.tasks_id_seq OWNED BY public.tasks.id;


--
-- Name: usage_info; Type: TABLE; Schema: public; Owner: funcx
--

CREATE TABLE public.usage_info (
    id bigint NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    total_functions integer,
    total_endpoints integer,
    total_users integer,
    total_core_hours double precision,
    total_invocations integer,
    functions_day integer,
    functions_week integer,
    functions_month integer,
    endpoints_day integer,
    endpoints_week integer,
    endpoints_month integer,
    users_day integer,
    users_week integer,
    users_month integer
);


ALTER TABLE public.usage_info OWNER TO funcx;

--
-- Name: usage_info_id_seq; Type: SEQUENCE; Schema: public; Owner: funcx
--

CREATE SEQUENCE public.usage_info_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.usage_info_id_seq OWNER TO funcx;

--
-- Name: usage_info_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: funcx
--

ALTER SEQUENCE public.usage_info_id_seq OWNED BY public.usage_info.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: funcx
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    username text,
    globus_identity text,
    created_at timestamp without time zone DEFAULT now(),
    namespace text,
    deleted boolean DEFAULT false
);


ALTER TABLE public.users OWNER TO funcx;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: funcx
--

CREATE SEQUENCE public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.users_id_seq OWNER TO funcx;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: funcx
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: auth_groups id; Type: DEFAULT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.auth_groups ALTER COLUMN id SET DEFAULT nextval('public.auth_groups_id_seq'::regclass);


--
-- Name: container_images id; Type: DEFAULT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.container_images ALTER COLUMN id SET DEFAULT nextval('public.container_images_id_seq'::regclass);


--
-- Name: containers id; Type: DEFAULT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.containers ALTER COLUMN id SET DEFAULT nextval('public.containers_id_seq'::regclass);


--
-- Name: function_auth_groups id; Type: DEFAULT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.function_auth_groups ALTER COLUMN id SET DEFAULT nextval('public.function_auth_groups_id_seq'::regclass);


--
-- Name: function_containers id; Type: DEFAULT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.function_containers ALTER COLUMN id SET DEFAULT nextval('public.function_containers_id_seq'::regclass);


--
-- Name: functions id; Type: DEFAULT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.functions ALTER COLUMN id SET DEFAULT nextval('public.functions_id_seq'::regclass);


--
-- Name: groups id; Type: DEFAULT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.groups ALTER COLUMN id SET DEFAULT nextval('public.groups_id_seq'::regclass);


--
-- Name: requests id; Type: DEFAULT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.requests ALTER COLUMN id SET DEFAULT nextval('public.requests_id_seq'::regclass);


--
-- Name: restricted_endpoint_functions id; Type: DEFAULT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.restricted_endpoint_functions ALTER COLUMN id SET DEFAULT nextval('public.restricted_endpoint_functions_id_seq'::regclass);


--
-- Name: results id; Type: DEFAULT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.results ALTER COLUMN id SET DEFAULT nextval('public.results_id_seq'::regclass);


--
-- Name: sites id; Type: DEFAULT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.sites ALTER COLUMN id SET DEFAULT nextval('public.sites_id_seq'::regclass);


--
-- Name: tasks id; Type: DEFAULT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.tasks ALTER COLUMN id SET DEFAULT nextval('public.tasks_id_seq'::regclass);


--
-- Name: usage_info id; Type: DEFAULT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.usage_info ALTER COLUMN id SET DEFAULT nextval('public.usage_info_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: action_instance action_instance_pkey; Type: CONSTRAINT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.action_instance
    ADD CONSTRAINT action_instance_pkey PRIMARY KEY (action_id);


--
-- Name: auth_groups auth_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.auth_groups
    ADD CONSTRAINT auth_groups_pkey PRIMARY KEY (id);


--
-- Name: container_images container_images_pkey; Type: CONSTRAINT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.container_images
    ADD CONSTRAINT container_images_pkey PRIMARY KEY (id);


--
-- Name: containers containers_pkey; Type: CONSTRAINT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.containers
    ADD CONSTRAINT containers_pkey PRIMARY KEY (id);


--
-- Name: function_auth_groups function_auth_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.function_auth_groups
    ADD CONSTRAINT function_auth_groups_pkey PRIMARY KEY (id);


--
-- Name: function_containers function_containers_pkey; Type: CONSTRAINT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.function_containers
    ADD CONSTRAINT function_containers_pkey PRIMARY KEY (id);


--
-- Name: functions functions_pkey; Type: CONSTRAINT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.functions
    ADD CONSTRAINT functions_pkey PRIMARY KEY (id);


--
-- Name: groups groups_pkey; Type: CONSTRAINT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_pkey PRIMARY KEY (id);


--
-- Name: requests requests_pkey; Type: CONSTRAINT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.requests
    ADD CONSTRAINT requests_pkey PRIMARY KEY (id);


--
-- Name: restricted_endpoint_functions restricted_endpoint_functions_pkey; Type: CONSTRAINT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.restricted_endpoint_functions
    ADD CONSTRAINT restricted_endpoint_functions_pkey PRIMARY KEY (id);


--
-- Name: results results_pkey; Type: CONSTRAINT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.results
    ADD CONSTRAINT results_pkey PRIMARY KEY (id);


--
-- Name: sites sites_pkey; Type: CONSTRAINT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.sites
    ADD CONSTRAINT sites_pkey PRIMARY KEY (id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: usage_info usage_info_pkey; Type: CONSTRAINT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.usage_info
    ADD CONSTRAINT usage_info_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: funcx
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_action_instance_action_id; Type: INDEX; Schema: public; Owner: funcx
--

CREATE INDEX ix_action_instance_action_id ON public.action_instance USING btree (action_id);


--
-- Name: ix_action_instance_request_id; Type: INDEX; Schema: public; Owner: funcx
--

CREATE INDEX ix_action_instance_request_id ON public.action_instance USING btree (request_id);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: funcx
--

REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO funcx;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- PostgreSQL database dump complete
--