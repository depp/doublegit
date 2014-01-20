# DoubleGit

We need to go deeper.

DoubleGit is a tool which allows you to track the version history of the version history in a Git repository.  Wait, what?  Why?

The purpose of this tool is extremely specialized: it is used for creating a synthetic Git repository, and tracking that synthetic history as it changes over time.  The history must be linear.  No merging is supported.

## The use case

Suppose you are writing a programming tutorial.  The tutorial is accompanied by a git repository, showing the steps in the tutorial.  Then you realize that you want to change the code in step #1.  You could rewrite the history to reflect the tutorial, but you lose the real history.

This is solved with DoubleGit.  Use DoubleGit to check your repository into a repository, rewrite history in the inner repository, and then export the new history to the outer repository.

## Instructions

There are two commands: extract and rebuild.  **Warning: These commands are destructive!**

The extract command extracts the commit history from a Git repository in a way that it can be restored.  It will **DELETE** the output directory if it exists and recreate it.

    $ ls
    my-repo
    $ path/to/doublegit/run.sh extract my-repo my-repo-history

The restore command rebuilds a repository from the extracted version.  It will **DELETE** the output repository if it exists and recreate it.

    $ ls
    my-repo
    my-repo-history
    $ path/to/doublegit/run.sh rebuild my-repo-history my-repo-copy
    ...
    $ ls
    my-repo
    my-repo-history
    my-repo-copy

The SHA-1 hashes of the recreated repository should match those of the original repository.

