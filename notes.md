# Notes on Progress

## Github Logistics

Need a way for the bot to not work on something that I am already working on.

So for the github integration, we should give the bot its OWN account. That way, we can assign it to tasks we want it to tackle, and on a task we pick up, we can just remove its assignment.

- Or, we could add another label called BOT_ALLOWED and it only codes based on that label. But the first option looks more appealing because then its like a real human helping.

If needed to make a new github account, let me know. Also, I will need to know things about like how to make it so there is no 2FA and that it can be automatically managed by the bot.

## Web UI

Should see when the agent will pick up its task next, if no task, is currently scheduled, then we should also see that.

There should also be a button to have the agent fetch the github to see if there are any new tasks to do when it runs next time. This shouldn't cost any API tokens because this should all just be hardcoded like fetching for issues and updating the task schedule for the agent.

Then, the task schedule should be viewable and manageable by the user on the web.

## Agent

Need to look at how the agent currently develops, but I don't think it actually runs the code it creates. We need to ensure that the agent does do the test code routine before it finalizes that it finished the task.

The current workflow shows that the AI should run tests. However, we need to verify that the AI actually makes tests for the code it wrote, and if possible, we should also have it just test the workflow in general (although maybe this part could be more optional because testing browser/web code is harder). I can definitely set up the miniPC or another computer with a GUI for web testing purposes.

Also, how is the code even compiling? I thought that aider-engine was the package and not aider. That is what it is in the requirements.txt. This is for file aider_engine.py.

Also, (maybe the code already does this) before the agent runs, we should fetch the issues from github one more time to make sure our task schedule is good.

## Logistics

The checkboxes in the ai-coding-agent-plan.md were not checked for up to and including phase 5. So, can you verify that they were implemented properly.

Also, we need to add a log file where it can log messages so I have an understanding of what is going on and can check on the status. This log file could also be viewable from the web UI for ease.

## Plan

After reviewing the above and implementing things wherever needed, we should just finish all the way to phase 6 and start integration testing it live. Also, we might need phase 6 to be done because it is the token limit phase and we absolutely don't want the agent to use more than its daily quota (and we need rate limiting).

The most important part is about how well the agent is able to develop and that the code the agent develops is actually good production code. Thus, this application should prioritize the ability for the agent to develop good code. It shouldn't prioritize how much code. So quality >> quantity.

Also, I need to understand the code somewhat as I have no idea what is happening. However, I'll explore that on my own time. Can you make an dissection.md file that explains the codebase to help me explore it later.

Phase 7 onwards is more optional for now/not needed in an MVP.
