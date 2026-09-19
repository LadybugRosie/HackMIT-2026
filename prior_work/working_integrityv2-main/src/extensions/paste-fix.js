// FILE: src/extensions/paste-fix.js

import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Slice, Fragment } from '@tiptap/pm/model';

export const PasteFix = Extension.create({
  name: 'pasteFix',

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('pasteFix'),
        props: {
          // This is the magic hook. It runs on every paste.
          transformPasted: (slice) => {
            // `slice.content` is a Fragment containing the pasted nodes.
            const { content } = slice;
            const newNodes = [];

            // We loop through the pasted nodes to find the actual content.
            content.forEach(node => {
              // If the pasted content is an entire page, we don't want the page
              // wrapper itself, we only want its content.
              if (node.type.name === 'page') {
                // Add all children of the page node to our new list.
                node.content.forEach(child => newNodes.push(child));
              } else {
                // If it's a regular node (paragraph, heading, etc.), just add it.
                newNodes.push(node);
              }
            });

            // Create a new, clean slice containing only the unwrapped content.
            const newSlice = new Slice(Fragment.from(newNodes), slice.openStart, slice.openEnd);
            
            // Return the fixed slice. Tiptap will now insert this instead.
            return newSlice;
          },
        },
      }),
    ];
  },
});