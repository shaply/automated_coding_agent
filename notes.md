# Notes on Progress

## Tasks for me

Consider setting up one of the laptops to enable browser support. Can the miniPC support browser? Check that. Although, perhaps browser support is too much anyways. After all, frontend should always just be done with a person present because LLMs aren't good with visuals.

## Agent

The agent didn't seem to either actually make changes to the file or it wasn't successful at committing the changes it made to the branch. Will need to look into that.

```log
2026-03-12 04:19:14,506  INFO      main  Generated 10-step plan.
2026-03-12 04:19:46,983  INFO      main  Plan approved. Starting implementation.
2026-03-12 04:19:46,990  INFO      main  Step 1/10: Identify all POST/PUT endpoints in `server.ts` that call `request.json()` without checking the `Content-Length` header.
2026-03-12 04:19:48,054  INFO      main  Step 1/10 complete (tests skipped).
2026-03-12 04:19:48,062  INFO      main  Step 2/10: Determine a reasonable limit for the request body size (e.g., 64 KB) and define it as a constant in `server.ts`.
2026-03-12 04:19:48,396  INFO      main  Step 2/10 complete (tests skipped).
2026-03-12 04:19:48,404  INFO      main  Step 3/10: Create a function in `server.ts` to check the `Content-Length` header and return a 413 Payload Too Large response if the limit is exceeded.
2026-03-12 04:19:48,584  INFO      main  Step 3/10 complete (tests skipped).
2026-03-12 04:19:48,592  INFO      main  Step 4/10: Modify each identified POST/PUT endpoint in `server.ts` to call the new function before calling `request.json()`.
2026-03-12 04:19:48,920  INFO      main  Step 4/10 complete (tests skipped).
2026-03-12 04:19:48,928  INFO      main  Step 5/10: Add error handling to each modified endpoint to handle cases where the request body size exceeds the limit.
2026-03-12 04:19:49,107  INFO      main  Step 5/10 complete (tests skipped).
2026-03-12 04:19:49,115  INFO      main  Step 6/10: Consider adding logging to track instances where the request body size limit is exceeded.
2026-03-12 04:19:49,444  INFO      main  Step 6/10 complete (tests skipped).
2026-03-12 04:19:49,452  INFO      main  Step 7/10: Review `server.ts` for any other potential security vulnerabilities related to request body size.
2026-03-12 04:19:49,632  INFO      main  Step 7/10 complete (tests skipped).
2026-03-12 04:19:49,640  INFO      main  Step 8/10: Update `README.md` to include information about the new request body size limit and how it is enforced.
2026-03-12 04:19:49,819  INFO      main  Step 8/10 complete (tests skipped).
2026-03-12 04:19:49,827  INFO      main  Step 9/10: Test the modified endpoints to ensure the request body size limit is enforced correctly.
2026-03-12 04:19:50,156  INFO      main  Step 9/10 complete (tests skipped).
2026-03-12 04:19:50,165  INFO      main  Step 10/10: Consider adding a configuration option to allow the request body size limit to be adjusted without modifying the code.
2026-03-12 04:19:50,344  INFO      main  Step 10/10 complete (tests skipped).
2026-03-12 04:19:50,353  INFO      main  Implementation complete. Awaiting final diff review.
2026-03-12 04:20:45,778  INFO      main  Diff approved. Task complete.
2026-03-12 04:20:45,779  INFO      main  Pushing branch …
2026-03-12 04:20:46,427  INFO      integrations.git_client  Pushed branch autodev/issue-22 to origin
2026-03-12 04:20:47,131  INFO      main  Branch pushed: autodev/issue-22
2026-03-12 04:20:47,641  ERROR     integrations.github_client  Failed to open PR: Validation Failed: 422 {"message": "Validation Failed", "errors": [{"resource": "PullRequest", "code": "custom", "message": "No commits between main and autodev/issue-22"}], "documentation_url": "https://docs.github.com/rest/pulls/pulls#create-a-pull-request", "status": "422"}
2026-03-12 04:20:47,642  INFO      main  PR creation failed: Validation Failed: 422 {"message": "Validation Failed", "errors": [{"resource": "PullRequest", "code": "custom", "message": "No commits between main and autodev/issue-22"}], "documentation_url": "https://docs.github.com/rest/pulls/pulls#create-a-pull-request", "status": "422"}
2026-03-12 04:20:47,650  INFO      main  Wiped ephemeral repo: /tmp/autodev-task-85e447f7-dbdc-4f11-b013-270fba8bfde7-dzeeselu
```

## Web UI

- Should be a more graphical interface to see at what stage of the workflow the agent is at compared to the other stages of the workflow.
- The web doesn't need a diff. Since we are doing github repositories now, we can just have it so that when the bot thinks its done, it pushes its code to the branch. The user can review the code, and if the code is not to the user's liking, the user can comment to the bot and then the bot will continue working on the code. Once the code is good, the user will tell the bot to create the PR, and once the user approves, the task is finally done. If the user doesn't approve and gives the bot another comment, the bot removes the PR and continues working on the branch.

## Plan

Now, we need to make the minor improvements and just test it to see if it is able to do its job properly.

Phase 7 onwards is more optional for now/not needed in an MVP.
