# Notes on Progress

## Github Integration

I think for now, I'm not going to do the github app method and just use my account. However, in order to differentiate me and the bot, can you add a config in the config.yml like differentiating_label and the point of it is that the bot will only work on issues that are assigned to my github account and have the label. For now, have that label's value be BOT_ASSIGNED.

## Web UI

The LOG viewing should be better. Should be able to filter logs based on LOG status. Also, there should be different colors associated with different types of logs. And, the log display should be bigger rather than that small window.

For the task scheduling, the dashboard should also have a box on the right side that displays the task queue. As in, what tasks in what order the agent will tackle.

## Logistics

We need to make sure there is enough logging statements to know whether the agent was able to utilize all of the daily API tokens efficiently.

Perhaps, on the web UI, there should also be a way to interract with the data in the SQLite database, in order to gather some quick statistics. Could be a new tab like 'agent statistics'.

## Plan

Now, we need to make the minor improvements and just test it to see if it is able to do its job properly.

Phase 7 onwards is more optional for now/not needed in an MVP.
