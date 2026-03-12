# Notes on Progress

## Tasks for me

Consider setting up one of the laptops to enable browser support.

## Agent

Can the agent run commands, and would it be in a containerized environment. Maybe we allow it to run commands in a containerized environment, so it is able to run the code it writes to make sure it compiles and also run tests.

## Web UI

Log should start at the bottom on website because it is most recent. Also, there should be a filter by date.

## Logistics

If the agent is allowed to run, then for some projects, there might be environment variables that are needed. And also, if we want to change any configurations, we have to go redeploy.

Perhaps, we should add a frontend page on web UI that allows us to edit the `backend/config.yaml` that is used by the program. Then, for github repos, we need a way to give environment variables. However, keep in mind that for the environment variables, some github repos will have multiple "programs" in it, so we can't just make a single place to add environment variables.

We also need a way to cleanly stop the program rather than just entering the minipc and ending the docker container, so we can deploy new versions without messing any state things up.

## Plan

Now, we need to make the minor improvements and just test it to see if it is able to do its job properly.

Phase 7 onwards is more optional for now/not needed in an MVP.
