---
id: git-version-control-commits-branches
title: "Git fundamentals: working tree, index, commits and branch history"
description: "Understand three Git states, reproducible commits, branches and merges, with a tested isolated repository workflow."
category: engineering
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-control-flow-functions, modular-programming-interfaces]
sources:
  - {title: "Pro Git — Recording Changes to the Repository", url: "https://git-scm.com/book/en/v2/Git-Basics-Recording-Changes-to-the-Repository", kind: "official Git reference book"}
  - {title: "Pro Git — Branches in a Nutshell", url: "https://git-scm.com/book/en/v2/Git-Branching-Branches-in-a-Nutshell", kind: "official Git reference book"}
  - {title: "Git — git-restore manual", url: "https://git-scm.com/docs/git-restore", kind: "official Git manual"}
  - {title: "Git — git-merge manual", url: "https://git-scm.com/docs/git-merge", kind: "official Git manual"}
---
A software project needs to preserve which change introduced a behavior and how one line of work relates to another. Saving copies named final, final2 or latest does not provide reliable provenance. Git provides **versioned snapshots and a history of commits**, but its three local states must be understood before commands can be used safely: the working tree, the index and the committed tree. This model precedes code review, branching policy and automated deployment [1][2].

## Three states describe a local change

The **working tree** holds the checked-out files a developer edits. The **index**, also called the staging area, records the exact candidate versions of files for the next commit. The current **HEAD commit** identifies a previously recorded snapshot. These can disagree: a file may be edited in the working tree, a different version staged in the index, and an earlier version stored in HEAD [1].

Consider note.txt at version A in the committed tree. Editing it produces working version B without changing the index. Running git add copies the current content B into the index. Editing the file again to version C then leaves C in the working tree but B in the index. Committing at that point records B, not C. This explains why running git status and inspecting both staged and unstaged differences is necessary before committing.

The index is not merely a boolean flag indicating that some file changed. It captures file content and associated information for a prospective tree. A commit describes a snapshot of tracked content, with parent references and metadata; it does not normally store a complete machine runtime state.

## What a commit records

A Git commit identifies a tree of repository content and generally one or more parents, together with metadata such as authorship and commit message. An initial commit has no parent; a conventional non-merge commit typically has one; a normal two-way merge commit can have two parents. This produces a **directed acyclic graph of commit ancestry**, not a linear list forced onto every contributor [2].

Content identity and commit identity are related but distinct: changing message, parent, timestamps or other commit metadata can produce a different commit ID even if the tree content remains unchanged. Therefore a commit hash identifies a history object, not an abstract claim that the software is correct or that it passed tests.

Git author metadata is not automatic verification of personal identity. Reviewing content and enforcing repository permissions or signed-commit policies are separate controls. The local example configures a synthetic identity only so that commits are reproducible without accessing a personal global configuration.

## Branches are movable references

A branch name is a reference to a commit, not another full copy of the project's files. When a developer checks out branch edit and commits, its reference moves forward. Meanwhile main may continue pointing at the original commit. The commits can later be related through a merge. The branch operation is efficient precisely because Git does not clone every version of every file into a separate directory [2].

HEAD usually identifies the currently checked-out branch. It can also refer directly to a commit in a detached-HEAD state, where new commits do not advance a named branch by default. Detached HEAD is useful for inspection but requires attention if new work needs to be retained.

A remote-tracking branch, such as origin/main, is a local record of a remote reference as of the last synchronization. It is not a continuously updated guarantee of the remote's current state. Fetch and push are separate operations; committing locally does not publish changes.

## Create a branch and merge a change

The following shell transcript is intended for a new, empty temporary directory. It uses Git's local files only and does not contact any remote. The main branch records the first snapshot; edit records a second version. Merging edit with no-fast-forward creates a merge commit with two parents. It is a demonstration of the history structure, not a recommended branching policy for every team.

~~~sh
git init -q
git config user.name "Local Example"
git config user.email "example@example.invalid"
printf 'first\n' > note.txt
git add -- note.txt
git commit -q -m "record first version"
git branch -M main
git switch -q -c edit
printf 'second\n' > note.txt
git add -- note.txt
git commit -q -m "change note"
git switch -q main
git merge -q --no-ff -m "merge edit" edit
git log --oneline --graph --all
git status --short
~~~

At the end, note.txt contains second, and the index and working tree are clean. The graph contains an initial commit, an edit commit on a branch and a merge commit. A normal merge can fast-forward without creating an extra commit when no histories diverged; no-fast-forward is chosen here specifically to make the two-parent structure observable [4].

## Merge is not a blind text append

When both branches modify the same overlapping region, Git may report a conflict requiring human resolution. The conflict indicates that the system cannot safely select a single content version automatically; it is not proof that either author is wrong. During a three-way merge the common ancestor and both sides provide inputs for deciding the final content [4].

Review the intended behavior, edit the conflicted file to a correct resolved version, add that version and finish the merge. For a conflicted merge, git merge --abort may be available, but operations with pre-existing uncommitted changes are riskier. Starting a merge from a clean working tree reduces ambiguity [4].

A merge commit records integration history. Rebasing is a different operation that recreates commits on another base and changes their identities. Force-pushing rewritten shared history may discard collaborators' work; it requires an explicit team policy rather than a casual convenience.

## Safe restoration and destructive operations

There are two distinct goals: remove content from the staging area while preserving edits, and replace working-tree content with a recorded version. The first can use git restore --staged for a file; the second can use git restore for the working-tree copy. The default source differs depending on options: staged restoration normally uses HEAD, while worktree restoration normally uses the index [3].

Restoring a working file can discard uncommitted edits. Commands that rewrite history or remove tracked files can cause harder-to-recover loss. Before modifying state, inspect git status, git diff and git diff --staged to establish which copy contains valuable work.

Git generally records tracked content, not automatically every untracked file. A staged secret can remain in history after it is deleted in a later commit, so never treat a later deletion as safe secret removal. Check ignored paths, reviews and protection policies, while recognizing that ignore rules do not retroactively untrack committed files.

## Tests, invariants and complexity limits

An independent test can initialize a repository in a temporary directory, record one file, stage one version, modify the working tree again and verify that the committed version equals the staged content rather than the later edit. Another test creates two branches and requires a merge commit with exactly two parents. These are behavioral tests of commands, not assumptions based on shell output formatting.

The history invariant is that each normal commit refers to a tree and parent objects from which its ancestry can be traced. A merge changes history structure without proving that the combined program passes tests. A code review should link changes to requirements and executable checks, not substitute the presence of a green branch name for evidence.

Storage and runtime depend on number and size of changed objects, history shape, compression and maintenance. Calling every Git operation O(1) just because a branch name is a reference would be inaccurate. Branch reference creation is cheap in the common model, but checking out thousands of files or merging conflicting trees requires more work.

## Exercises and verification

1. Stage version B of a file, change the working copy to C and explain which version will be committed.
2. Inspect staged and unstaged diffs independently and identify their reference states.
3. Count the parents of a merge commit; compare this with a fast-forward update.
4. Explain why a new local commit is not automatically visible on the remote server.
5. Demonstrate unstaging a file without destroying its working-tree edits [3].
6. Explain why resolving a merge conflict and passing behavioral tests are separate responsibilities.

Continue with [module boundaries](/en/topics/modular-programming-interfaces/), [incremental builds](/en/topics/build-dependency-graphs-gnu-make/) and [software project lifecycle](/en/topics/software-project-lifecycle/).