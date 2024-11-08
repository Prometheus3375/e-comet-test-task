begin;
create table repositories
(
    id          bigint generated always as identity,
    repo        varchar(100) not null,
    owner       varchar(39)  not null,
    stars       integer      not null,
    watchers    integer      not null,
    forks       integer      not null,
    open_issues integer      not null,
    language    varchar(100),
    primary key (id),
    constraint repo_owner_tuple unique (repo, owner)
);
create table previous_places
(
    repo_id bigint references repositories (id),
    place   bigint not null,
    primary key (repo_id)
);
create table activity
(
    repo_id bigint references repositories (id),
    date    date               not null,
    commits integer            not null,
    authors varchar(100) array not null,
    constraint repo_id_date_tuple unique (repo_id, date)
);
commit;
