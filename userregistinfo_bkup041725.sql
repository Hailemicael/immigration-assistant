PGDMP                      }           userregistinfo    17.4    17.4                0    0    ENCODING    ENCODING        SET client_encoding = 'UTF8';
                           false                        0    0 
   STDSTRINGS 
   STDSTRINGS     (   SET standard_conforming_strings = 'on';
                           false            !           0    0 
   SEARCHPATH 
   SEARCHPATH     8   SELECT pg_catalog.set_config('search_path', '', false);
                           false            "           1262    16388    userregistinfo    DATABASE     t   CREATE DATABASE userregistinfo WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'en-US';
    DROP DATABASE userregistinfo;
                     postgres    false                        2615    16389    immigration_agent    SCHEMA     !   CREATE SCHEMA immigration_agent;
    DROP SCHEMA immigration_agent;
                     postgres    false            �            1259    16391    users    TABLE     �   CREATE TABLE immigration_agent.users (
    id integer NOT NULL,
    email text NOT NULL,
    first_name text NOT NULL,
    last_name text NOT NULL,
    summ_last_convo text,
    questions text,
    answers text
);
 $   DROP TABLE immigration_agent.users;
       immigration_agent         heap r       postgres    false    6            �            1259    16390    users_id_seq    SEQUENCE     �   CREATE SEQUENCE immigration_agent.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
 .   DROP SEQUENCE immigration_agent.users_id_seq;
       immigration_agent               postgres    false    6    219            #           0    0    users_id_seq    SEQUENCE OWNED BY     S   ALTER SEQUENCE immigration_agent.users_id_seq OWNED BY immigration_agent.users.id;
          immigration_agent               postgres    false    218            �           2604    16394    users id    DEFAULT     z   ALTER TABLE ONLY immigration_agent.users ALTER COLUMN id SET DEFAULT nextval('immigration_agent.users_id_seq'::regclass);
 B   ALTER TABLE immigration_agent.users ALTER COLUMN id DROP DEFAULT;
       immigration_agent               postgres    false    219    218    219                      0    16391    users 
   TABLE DATA           q   COPY immigration_agent.users (id, email, first_name, last_name, summ_last_convo, questions, answers) FROM stdin;
    immigration_agent               postgres    false    219   �       $           0    0    users_id_seq    SEQUENCE SET     E   SELECT pg_catalog.setval('immigration_agent.users_id_seq', 3, true);
          immigration_agent               postgres    false    218            �           2606    16398    users users_pkey 
   CONSTRAINT     Y   ALTER TABLE ONLY immigration_agent.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);
 E   ALTER TABLE ONLY immigration_agent.users DROP CONSTRAINT users_pkey;
       immigration_agent                 postgres    false    219               D   x�3�����˫�K��/IJ��qH,q�s��KM)��Kq�A�8c� �ˈ,]�Ⱥ*���ıh����� F�43     