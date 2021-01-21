# message-channel

![PyPI](https://img.shields.io/pypi/v/python-message-channel)
![PyPI - License](https://img.shields.io/pypi/l/python-message-channel)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/python-message-channel)
![Test](https://github.com/fixpoint/python-message-channel/workflows/Test/badge.svg)

This library provides a message channel object which subtract particular messages from mass of messages. It's like _group by_ of SQL or ReactiveX but for asynchronous reader.

## Installation

```
pip install python-message-channel
```

## Usage

For example, assume that you have a string stream which messages are prefixed by `a`, `b`, ... `e` and you'd like to split subchannels for messages prefixed by `b` or `d` like below.

```
=============================================
---------------------------------> a:foo
--------------------+
--------------------|------------> c:foo
--------------------|------------> d:foo
--------------------|------------> e:foo
====================|========================
channel             |
                   =|========================
                    +------------> b:foo
                   ==========================
                   subchannel `m.startswith('b')`
```

This library is a tool for handling such situation.
First, create a `Channel` instance from a steram reader and you can receive messages by
`channel.recv()` method.
In this example, we use `asyncio.Queue` as a stream.

```python
import asyncio

from message_channel import Channel

async def main():
    # Create original stream
    stream = asyncio.Queue()

    # Create stream reader
    async def reader():
        return await stream.get()

    # Create stream channel
    async with Channel(reader) as channel:
        stream.put_nowait('a:foo')
        stream.put_nowait('b:foo')
        stream.put_nowait('c:foo')
        stream.put_nowait('d:foo')
        stream.put_nowait('e:foo')
        assert (await channel.recv()) == 'a:foo'
        assert (await channel.recv()) == 'b:foo'
        assert (await channel.recv()) == 'c:foo'
        assert (await channel.recv()) == 'd:foo'
        assert (await channel.recv()) == 'e:foo'


if __name__ == '__main__':
    asyncio.run(main())
```

And you can _split_ the channel by `channel.split()` method by a predicator like

```python
    async with Channel(reader) as channel:
        def predicator(m):
            return m.startswith('b:')

        async with channel.split(predicator) as sub:
            stream.put_nowait('a:foo')
            stream.put_nowait('b:foo')
            stream.put_nowait('c:foo')
            stream.put_nowait('d:foo')
            stream.put_nowait('e:foo')
            # sub receive messages starts from 'b:'
            assert (await sub.recv()) == 'b:foo'
            # channel (original) receive messages other than above
            assert (await channel.recv()) == 'a:foo'
            assert (await channel.recv()) == 'c:foo'
            assert (await channel.recv()) == 'd:foo'
            assert (await channel.recv()) == 'e:foo'
```

## API documentation

https://fixpoint.github.io/python-message-channel/

powered by [pdoc](https://pdoc3.github.io/pdoc/).

## License

Distributed under the terms of the [MIT License](./LICENSE)
