# Production Release Prep QA Pass

## All pages

:white_check_mark:- We need to realign any "third-party" wording/phrasing to better represenet "indie game developers" and "indie games/content". Lean hard into the fact that BE supports indies.
:white_check_mark:- This panel is repeated at least once between the home page and `/offerings`. It should just be on the home page as the footer should cover the rest of the pages. See "C:\Users\matt\Pictures\Screenshots\BE Production QA Pass\RepeatedPanel.png"

## Data Seeding

- If not done already, we should update our data seeding for testing so that it includes entries for spotlights as well as entries and example media for the new title details media carousel.
- All seeding should only be done in local and staging environments; production environment **should not be seeded**.

### Footer

:white_check_mark:- The "preview environment" section should be removed for produciton release
:white_check_mark:- All of the pages being repeated in the footer feels redundant and cluttered. Many of those are already available in the nav header which stays visible at all times. Leave `Contact Us` and `Privacy`, and any other pages that aren't already able to be reached otherwise, but the other page links that appear in the top-center of the footer. See "C:\Users\matt\Pictures\Screenshots\BE Production QA Pass\FooterClutter.png"

## Home Page

:white_check_mark:- The offerings section listed on the home page feels very redundant to the `/offerings` page. See "C:\Users\matt\Pictures\Screenshots\BE Production QA Pass\HomePageOfferingsSection.png". Instead, it would be nice to apply a very similar thing like we've done with the game title spotlight banner area and have a carousel on the home page spotlighting certain offerings. We'd want this to be dynamic as well so that we wouldn't have to manually update and release every time we want to change what offering is spotlighted. We should add capability in the database to data-drive our offerings. Each part of an offering card should be configurable as a field and we should be able to use SQL queries to change what offerings are currently spotlighted. While I know these additions will have to be exposed in the API, they **should not** be added as part of the *publicly documented* API. The carousel should have the same style and rules as the one we added to `/browse`, but not be nearly as big.

## /browse

:white_check_mark:- Let's ditch the `Browse` header and subtitle so the top of the page is just immediatley the spotlight banner
:white_check_mark:- The timer for the spotlight cycle doesn't seem to be resetting when the user manually navigates. Sometimes they navigate and it almost immediatley progresses; other times it waits longer
:white_check_mark:- At a low media breakpoint, a horizontal scrollbar is appearing above the page, under the nav bar. This is not ideal and we'd prefer it go away. See screenshot "C:\Users\matt\Pictures\Screenshots\BE Production QA Pass\HorizBarOnBrowsePage.png"

:white_check_mark:- See "C:\Users\matt\Pictures\Screenshots\BE Production QA Pass\DefaultTitleBrowseCard.png". If a title was created without any media, a default image for the title card is displaying with text in the bottom that is under the title's overlay. This looks really bad right now. The card image shouldn't have any text built in like that which goes under the overlay, as that's what the overlay is for. The default image doesn't really vibe with the rest of the site. It would be nice to have a standard one with a style that fits in as a default. Maybe we could use a colored icon like any of the ones shown in this image of icons that are available from https://fonts.google.com/icons?icon.size=24&icon.color=%23FFFFFF&icon.query=game? One of the chess pieces could be a good fit, since Board is platform for using physical pieces. See "C:\Users\matt\Pictures\Screenshots\BE Production QA Pass\CardIconPossibilities.png"

### Title Quick View Modal

See "C:\Users\matt\Pictures\Screenshots\BE Production QA Pass\TitleQuickViewModal.png" for current screenshot

:white_check_mark:- The title description is not respecting the formatting that the developer entered in the title creation, particularly where whitespace is concerned. We should ideally take the format of the text as they entered it, and hopefully support rich text tags/formatting as well. This applies here as well as on the title details page and the developer's title metadata, likely because of how it's stored in the database.
:white_check_mark:- The "This title is coming soon. It remains visible here because it is already in your library or wishlist." is just ugly and also incorrect. That whole yellow panel section should be removed, in favor of a callout chip in the top-left of the title hero image that says "Coming Soon", similar to how it is in the card hover description on the browse page.

### Title Details Page

See "C:\Users\matt\Pictures\Screenshots\BE Production QA Pass\TitleDetailsUpdates.png"

- The red arrows point to things that should be removed:
  - Current version below wishlist/library/report icons
  - Small chip in top-left of preview media thumbnail
  
:white_check_mark:- Yellow box around `Availability` indicates this row should be removed. Instead, if a title is available now, nothing special should be shown anywhere. If the title is "Coming Soon", a noticeable chip should be added in the top-right of the preview area to call out that it is coming soon
:white_check_mark:- We need more media examples added so that we can better test and understand the functionality of the new carousel. For example, if the carousel has a LOT of images/videos, what is the behavior? We would want it to be scrollable with no visible scroll bars, but the overflow hidden so it becomes clear there are more previews available.
:white_check_mark:- We need examples of a video media to properly test what that looks like.
:white_check_mark:- See "C:\Users\matt\Pictures\Screenshots\BE Production QA Pass\TitleDetailsComingSoonChip.png". For a coming soon title, move the existing "Coming Soon" chip to the top-right of the preview area, as mentioned above.

## /install-guide

:white_check_mark:- We need to update the page with new guidance that aligns with our found conclusion that Board does not support on-device install as we hoped. The current "We know this is cumbersome" panel should just be removed and the instructions updated to match our expected adjustment to Board's restrictions:

  1. Browse/Search/Discover indie games on BE
  2. Choose a title and download it from the developer on your PC (that last part is the important one, as it must be installed via `bdb` on their PC)
  3. Download the installer (current step #2 is still applicable as-is)
  4. Install on Board (current step #3 still applicable as-is)
  
## /studios

### Studio Details Page

See "C:\Users\matt\Pictures\Screenshots\BE Production QA Pass\CurrentStudioDetailsPage.png" for current screenshot
See the following screenshots as examples for the following requests:
  - "C:\Users\matt\Pictures\Screenshots\BE Production QA Pass\SteamStudioDetailsBanner.png"
  - "C:\Users\matt\Pictures\Screenshots\BE Production QA Pass\SteamStudioAboutPage.png"

- We'd like to rework UI a bit for this page to look more like this Steam example
  :white_check_mark:- `Follow Studio` should just say `Follow`
  :white_check_mark:- `Following Studio` should just say `Following`
  :white_check_mark:- Number of followers should be added to the right of the following
  :white_check_mark:- Tighten up the studio banner so it's not nearly as large
  :white_check_mark:- Add a tabbed nav bar below the banner that has `Catalog` and `About` tabs for now, but may be added to later. The `Catalog` tab should be the default active tab, and should display the currently existing search and browse capability for studio. The `About` tab should have the studio description moved to it and contain any additional useful Studio details we have, including the studio links that are not popularly known and already listed on the studio banner. Leave those popularly known links up in the banner where they are. This will enable us later to add new features like additional tabs for Studios, Studio announcements, etc.
  
## /player

### Studios You Follow

See "C:\Users\matt\Pictures\Screenshots\BE Production QA Pass\StudiosYouFollow.png" for current screenshot

- Don't have the full studio description here. Just put the Studio logo, avatar, and hero thumbnail (Avatar left, with Studio logo above studio thumbnail in a group to right of avatar)

## /develop

:white_check_mark:- Page route should be changed to `/developer` and all links/references updated

### Studios

:white_check_mark:- The `Preview Studio` button and the modal that goes with it should be removed. Instead, there should be an `Open Studio` button that takes them to the actual studio details page so they can see how it really looks. The preview modal was misleading in how the final page would look.
:white_check_mark:- We need a way for users to discover and follow studios that don't have any titles yet. The only way to do this currently is by the user knowing the studio name and guessing what the slug might be in order to manually type in the URL (e.g. `/studios/blue-fairy-games`).

### Titles

#### Overview

See "C:\Users\matt\Pictures\Screenshots\BE Production QA Pass\DeveloperTitleOverview.png"

:white_check_mark:- Developer needs a convenient button added to go view the title details page so they can see how it looks. This should only be available if the title is active and listed.

### Releases

#### Create Release

See "C:\Users\matt\Pictures\Screenshots\BE Production QA Pass\CreateReleaseScreen.png"

- For the expiration date field:
  :white_check_mark:- Remove "and time" from the field name; it's not necessary as it's clear
  :white_check_mark:- It would be nice to have a standard popup calendar to pick a date like other sites. Surely there's an open source solution for this in `npm` we can utilize...