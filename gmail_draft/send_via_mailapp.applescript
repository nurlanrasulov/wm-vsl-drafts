#!/usr/bin/env osascript
-- Find COCA COLA VSL REPORT draft, remove Wolt analytics recipient, optionally send.

on run argv
    set draftSubject to "COCA COLA VSL REPORT"
    set excludeEmail to "no-reply.analytics@wolt.com"
    set dryRun to false

    if (count of argv) > 0 then
        set draftSubject to item 1 of argv
    end if
    if (count of argv) > 1 then
        set excludeEmail to item 2 of argv
    end if
    if (count of argv) > 2 then
        set dryRun to (item 3 of argv is "dry-run")
    end if

    tell application "Mail"
        set targetMessage to missing value
        set targetAccount to ""

        repeat with acct in accounts
            try
                set draftBox to mailbox "Drafts" of acct
                repeat with msg in (messages of draftBox)
                    set msgSubject to subject of msg
                    if msgSubject is draftSubject or msgSubject contains draftSubject then
                        set targetMessage to msg
                        set targetAccount to name of acct
                        exit repeat
                    end if
                end repeat
            end try
            if targetMessage is not missing value then exit repeat
        end repeat

        if targetMessage is missing value then
            error "No draft found with subject: " & draftSubject
        end if

        my removeRecipient(targetMessage, excludeEmail, "to recipients")
        my removeRecipient(targetMessage, excludeEmail, "cc recipients")
        my removeRecipient(targetMessage, excludeEmail, "bcc recipients")

        set recipientSummary to my summarizeRecipients(targetMessage)

        if dryRun then
            return "DRY_RUN|" & targetAccount & "|" & recipientSummary
        end if

        send targetMessage
        return "SENT|" & targetAccount & "|" & recipientSummary
    end tell
end run

on removeRecipient(msg, excludeEmail, recipientType)
    tell application "Mail"
        if recipientType is "to recipients" then
            set recips to to recipients of msg
        else if recipientType is "cc recipients" then
            set recips to cc recipients of msg
        else
            set recips to bcc recipients of msg
        end if

        repeat with r in recips
            if (address of r as text) is excludeEmail then
                delete r
            end if
        end repeat
    end tell
end removeRecipient

on summarizeRecipients(msg)
    tell application "Mail"
        set parts to {}
        repeat with r in to recipients of msg
            set end of parts to (address of r as text)
        end repeat
        return "To: " & my joinList(parts, ", ")
    end tell
end summarizeRecipients

on joinList(theList, delimiter)
    set AppleScript's text item delimiters to delimiter
    set out to theList as text
    set AppleScript's text item delimiters to ""
    return out
end joinList
